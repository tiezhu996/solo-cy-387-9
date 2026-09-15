"""整改领域服务：领取整改单、提交处理结果、巡检员复验、重新分派。"""

from django.db import transaction
from django.utils import timezone

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.apps.inspection.models import InspectionTask
from app.constants.enums import (
    ORDER_PENDING,
    ORDER_PROCESSING,
    ORDER_RETURNED,
    ORDER_SUBMITTED,
    ORDER_VERIFIED,
    ORDER_CLOSED,
    TASK_RETURNED,
    TASK_SUBMITTED,
)
from app.constants.errors import BusinessError
from .models import RecheckRecord, RectificationOrder, RectificationResolution


@transaction.atomic
def claim_order(order_id, rectifier):
    """并发安全领取整改单，单条原子条件更新保证只有一名整改人成功。

    可领取状态：
    - pending：新生成待整改，领取后进入 processing；
    - returned：复验驳回需重新整改（可能因原整改人停用而退回池中），
      新整改人领取后进入 processing，轮次保留以便继续当轮/下一轮处理。
    submitted（待复验）不进整改领取池——该阶段由巡检员复验，归属交接随任务进行。

    领取与停用共享用户行级串行边界：先锁本人用户行并复查启用，再更新整改单。
    """
    from django.db.models import Value
    from app.apps.users.locking import lock_active_user

    # 第一条写语句：锁本人用户行 + 复查启用状态（与停用互斥串行）
    lock_active_user(rectifier.id)

    claimable = (ORDER_PENDING, ORDER_RETURNED)
    updated = RectificationOrder.objects.filter(
        pk=order_id, assignee__isnull=True, status__in=claimable
    ).update(
        assignee=rectifier, status=ORDER_PROCESSING, claimed_at=timezone.now()
    )
    if updated == 0:
        if not RectificationOrder.objects.filter(pk=order_id).exists():
            raise BusinessError('ORDER_NOT_FOUND', 404)
        raise BusinessError('ORDER_NOT_CLAIMABLE', 409)

    order = RectificationOrder.objects.get(pk=order_id)
    returned = order.round > 1
    record_history(
        StatusHistory.TARGET_ORDER, order.id, 'claim',
        from_status=ORDER_RETURNED if returned else ORDER_PENDING,
        to_status=ORDER_PROCESSING,
        actor=rectifier,
        detail=f'{rectifier.name}领取整改单' + ('，承接驳回后重新整改' if returned else ''),
    )
    return order


@transaction.atomic
def submit_resolution(order_id, rectifier, note, photos):
    order = RectificationOrder.objects.select_for_update().filter(pk=order_id).first()
    if order is None:
        raise BusinessError('ORDER_NOT_FOUND', 404)
    if order.assignee_id != rectifier.id:
        raise BusinessError('NOT_ORDER_OWNER', 403)
    if order.status not in (ORDER_PROCESSING, ORDER_RETURNED):
        raise BusinessError('ORDER_NOT_PROCESSING', 409)
    if not (note or '').strip():
        raise BusinessError('VALIDATION', 400, '请填写处理说明')

    from_status = order.status
    resolution = RectificationResolution.objects.create(
        order=order, round=order.round, rectifier=rectifier,
        note=note.strip(), photos=photos or [],
    )
    order.status = ORDER_SUBMITTED
    order.submitted_at = timezone.now()
    order.save(update_fields=['status', 'submitted_at', 'updated_at'])
    record_history(
        StatusHistory.TARGET_ORDER, order.id, 'submit_resolution',
        from_status=from_status, to_status=ORDER_SUBMITTED, actor=rectifier,
        detail=f'提交第 {order.round} 轮整改结果：{resolution.note}',
    )
    return order


@transaction.atomic
def recheck_order(order_id, inspector, passed, note=''):
    """巡检员复验：通过后置为 verified（任务可关闭）；驳回则回到整改人重做。"""
    order = RectificationOrder.objects.select_for_update().filter(pk=order_id).first()
    if order is None:
        raise BusinessError('ORDER_NOT_FOUND', 404)
    task = InspectionTask.objects.select_for_update().get(pk=order.task_id)
    if task.assignee_id != inspector.id:
        raise BusinessError('NOT_TASK_OWNER', 403, '只有该任务的巡检员可以复验')
    if order.status != ORDER_SUBMITTED:
        raise BusinessError('ORDER_NOT_RECHECKABLE', 409)

    RecheckRecord.objects.create(
        order=order, round=order.round, inspector=inspector,
        passed=passed, note=note or '',
    )
    order_from = order.status

    if passed:
        order.status = ORDER_VERIFIED
        order.verified_at = timezone.now()
        order.save(update_fields=['status', 'verified_at', 'updated_at'])
        record_history(
            StatusHistory.TARGET_ORDER, order.id, 'recheck_pass',
            from_status=order_from, to_status=ORDER_VERIFIED, actor=inspector,
            detail=f'第 {order.round} 轮复验通过' + (f'：{note}' if note else ''),
        )
        open_orders = task.rectification_orders.exclude(status__in=(ORDER_VERIFIED, ORDER_CLOSED))
        if not open_orders.exists():
            from app.apps.escalation.services import resolve_open_for_target
            resolve_open_for_target('rectification_order', order.id)
            record_history(
                StatusHistory.TARGET_TASK, task.id, 'all_verified',
                from_status=task.status, to_status=task.status, actor=inspector,
                detail='全部整改单复验通过，可以关闭任务',
            )
    else:
        order.round += 1
        order.status = ORDER_RETURNED
        order.save(update_fields=['status', 'round', 'updated_at'])
        task.status = TASK_RETURNED
        task.save(update_fields=['status', 'updated_at'])
        record_history(
            StatusHistory.TARGET_ORDER, order.id, 'recheck_reject',
            from_status=order_from, to_status=ORDER_RETURNED, actor=inspector,
            detail=f'第 {order.round - 1} 轮复验驳回，进入第 {order.round} 轮整改：{note or "未通过"}',
        )
        record_history(
            StatusHistory.TARGET_TASK, task.id, 'recheck_reject',
            from_status=TASK_SUBMITTED, to_status=TASK_RETURNED, actor=inspector,
            detail=f'整改单 {order.code} 复验驳回，任务重新整改',
        )
    return order


@transaction.atomic
def reassign_order(order_id, manager, new_rectifier):
    if new_rectifier.role != 'rectifier' or not new_rectifier.is_active:
        raise BusinessError('ROLE_MISMATCH', 400, '只能重新分派给启用中的整改人')
    order = RectificationOrder.objects.select_for_update().filter(pk=order_id).first()
    if order is None:
        raise BusinessError('ORDER_NOT_FOUND', 404)
    if order.status in (ORDER_VERIFIED, ORDER_CLOSED):
        raise BusinessError('ORDER_NOT_CLAIMABLE', 409, '已闭环的整改单不能重新分派')

    old = order.assignee
    old_status = order.status
    order.assignee = new_rectifier
    if order.status == ORDER_PENDING:
        order.status = ORDER_PROCESSING
        order.claimed_at = timezone.now()
    order.save()
    record_history(
        StatusHistory.TARGET_ORDER, order.id, 'reassign',
        from_status=old_status, to_status=order.status, actor=manager,
        detail=f'重新分派：{old.name if old else "公共池"} → {new_rectifier.name}',
    )
    return order
