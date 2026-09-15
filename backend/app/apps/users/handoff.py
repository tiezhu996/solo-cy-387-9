"""人员停用与待办交接。

停用巡检员/整改人时，必须在同一事务内把其名下未完成待办交给指定接管人或退回
公共池，否则待办会挂在停用账号名下形成死信。

并发安全（跨账号）：
- 涉及多个账号时，事务按用户 id 升序依次锁定用户行（固定加锁顺序，杜绝死锁）；
- 接管写入前在接管人锁内**重新确认其仍启用**：若接管人正被并发停用，本笔
  交接整体失败回滚，不留半完成记录；
- 资源行更新只作用于「当前归属=被停用者」的行，affected=0 不改数据也不写历史；
- 原处理记录与状态历史只增不改；重新启用不自动拿回已释放待办。
"""

from django.db import transaction
from django.db.models import Case, CharField, DateTimeField, F, Value, When
from django.utils import timezone

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.apps.escalation.services import resolve_open_for_target
from app.apps.inspection.models import InspectionTask
from app.apps.rectification.models import RectificationOrder
from app.apps.users.locking import lock_active_target, lock_user
from app.apps.users.models import User
from app.constants.errors import BusinessError


@transaction.atomic
def deactivate_and_handoff(user_id, manager, takeover_user_id=None):
    """停用人员并交接其在办待办（单事务，要么全成要么全回滚）。

    takeover_user_id 为空：在办任务/整改单退回公共池，可被重新领取。
    takeover_user_id 非空：直接归属接管人（须同角色、启用中、非本人）。
    """
    now = timezone.now()
    takeover = None

    takeover_id = int(takeover_user_id) if takeover_user_id else None
    if takeover_id is not None and takeover_id == int(user_id):
        raise BusinessError('ROLE_MISMATCH', 400, '接管人不能是被停用人员本人')

    # —— 按用户 id 升序固定加锁，杜绝跨账号死锁；接管人在锁内复核仍启用 ——
    if takeover_id is None:
        user = lock_user(user_id)
    elif takeover_id < int(user_id):
        takeover = lock_active_target(takeover_id)
        user = lock_user(user_id)
    else:
        user = lock_user(user_id)
        takeover = lock_active_target(takeover_id)

    if not user.is_active:
        # 已停用：幂等返回，不重复交接
        return {'user': user, 'takeover': None, 'task_count': 0,
                'order_count': 0, 'changed': False}

    if takeover is not None and takeover.role != user.role:
        raise BusinessError('ROLE_MISMATCH', 400, '接管人角色与被停用人员不一致')

    task_count = _handoff_tasks(user, takeover, manager, now)
    order_count = _handoff_orders(user, takeover, manager, now)

    # 资源全部交接完成后才翻转停用者；任一步抛错则整体回滚（账号也不会被停用）
    user.is_active = False
    user.save(update_fields=['is_active'])

    where = f'；交接巡检任务 {task_count} 个、整改单 {order_count} 张'
    where += f'，接管人：{takeover.name}' if takeover else '，均已退回公共待领池'
    record_history(
        'user', user.id, 'user_disable', actor=manager,
        detail=f'{user.name} 账号已停用{where}',
    )

    return {'user': user, 'takeover': takeover, 'task_count': task_count,
            'order_count': order_count, 'changed': True}


def _handoff_tasks(user, takeover, manager, now):
    """逐条条件交接：UPDATE ... WHERE pk=? AND assignee=user。

    仅当该行确由本事务交接（affected=1）才写历史、解除升级。若并发领取已把
    任务改到他人名下，affected=0：既不改数据也不写「幻象」交接记录。
    """
    ids = list(
        InspectionTask.objects.filter(assignee=user).exclude(status='done')
        .values_list('id', flat=True)
    )
    count = 0
    for task_id in ids:
        # 同一写事务内先读当前状态/期限（快照一致、写锁已持有）
        current = InspectionTask.objects.filter(pk=task_id).values('status', 'due_at').first()
        if current is None:
            continue
        from_status = current['status']
        qs = InspectionTask.objects.filter(pk=task_id, assignee=user).exclude(status='done')
        if takeover is not None:
            affected = qs.update(
                assignee=takeover,
                claimed_at=Case(
                    When(status='pending', then=Value(now)),
                    default=F('claimed_at'), output_field=DateTimeField(),
                ),
                status=Case(
                    When(status='pending', then=Value('claimed')),
                    default=F('status'), output_field=CharField(),
                ),
            )
            if not affected:
                continue  # 已被并发领取改走，不动
            to_status = 'claimed' if from_status == 'pending' else from_status
            detail = (
                f'原巡检员{user.name}停用，任务交接给{takeover.name}接管，'
                f'巡检期限保持 {timezone.localtime(current["due_at"]):%Y-%m-%d %H:%M}'
            )
            action = 'handoff_user'
        else:
            affected = qs.update(
                assignee=None,
                claimed_at=Case(
                    When(status__in=['pending', 'claimed'], then=Value(None)),
                    default=F('claimed_at'), output_field=DateTimeField(),
                ),
                status=Case(
                    When(status__in=['pending', 'claimed'], then=Value('pending')),
                    default=F('status'), output_field=CharField(),
                ),
            )
            if not affected:
                continue
            to_status = 'pending' if from_status in ('pending', 'claimed') else from_status
            detail = (
                f'原巡检员{user.name}停用，任务退回公共待领池，'
                f'巡检期限保持 {timezone.localtime(current["due_at"]):%Y-%m-%d %H:%M}'
            )
            action = 'handoff_pool'
        record_history(
            StatusHistory.TARGET_TASK, task_id, action,
            from_status=from_status, to_status=to_status, actor=manager, detail=detail,
        )
        resolve_open_for_target('task', task_id, actor=manager, note=detail)
        count += 1
    return count


def _handoff_orders(user, takeover, manager, now):
    ids = list(
        RectificationOrder.objects.filter(assignee=user)
        .exclude(status__in=['verified', 'closed']).values_list('id', flat=True)
    )
    count = 0
    for order_id in ids:
        current = RectificationOrder.objects.filter(pk=order_id).values('status', 'due_at').first()
        if current is None:
            continue
        from_status = current['status']
        qs = (
            RectificationOrder.objects.filter(pk=order_id, assignee=user)
            .exclude(status__in=['verified', 'closed'])
        )
        if takeover is not None:
            affected = qs.update(
                assignee=takeover,
                claimed_at=Case(
                    When(status='pending', then=Value(now)),
                    default=F('claimed_at'), output_field=DateTimeField(),
                ),
                status=Case(
                    When(status='pending', then=Value('processing')),
                    default=F('status'), output_field=CharField(),
                ),
            )
            if not affected:
                continue
            to_status = 'processing' if from_status == 'pending' else from_status
            detail = (
                f'原整改人{user.name}停用，整改单交接给{takeover.name}接管，'
                f'整改期限保持 {timezone.localtime(current["due_at"]):%Y-%m-%d %H:%M}'
            )
            action = 'handoff_user'
        else:
            affected = qs.update(
                assignee=None,
                claimed_at=Case(
                    When(status__in=['pending', 'processing', 'returned'], then=Value(None)),
                    default=F('claimed_at'), output_field=DateTimeField(),
                ),
                status=Case(
                    When(status__in=['pending', 'processing', 'returned'], then=Value('pending')),
                    default=F('status'), output_field=CharField(),
                ),
            )
            if not affected:
                continue
            if from_status in ('pending', 'processing', 'returned'):
                to_status = 'pending'
            else:
                to_status = from_status
            detail = (
                f'原整改人{user.name}停用，整改单退回公共待领池，'
                f'整改期限保持 {timezone.localtime(current["due_at"]):%Y-%m-%d %H:%M}'
            )
            action = 'handoff_pool'
        record_history(
            StatusHistory.TARGET_ORDER, order_id, action,
            from_status=from_status, to_status=to_status, actor=manager, detail=detail,
        )
        resolve_open_for_target('rectification_order', order_id, actor=manager, note=detail)
        count += 1
    return count
