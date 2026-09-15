"""巡检任务领域服务：发布、领取、提交、改期、重新分派、关闭。

所有写操作都在数据库事务内完成，并同步写入状态历史；领取采用条件更新，
保证重复领取或并发领取时只有一人成功。
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from app.apps.audit.services import record_history
from app.apps.audit.models import StatusHistory
from app.apps.organization.models import Area, Building
from app.apps.inspection.models import (
    InspectionItemResult,
    InspectionSubmission,
    InspectionTask,
)
from app.apps.rectification.models import RectificationOrder
from app.constants.enums import (
    RESULT_ISSUE,
    TASK_CLAIMED,
    TASK_DONE,
    TASK_PENDING,
    TASK_SUBMITTED,
)
from app.constants.errors import BusinessError

# 默认整改期限（天），提交异常时给整改单设置
DEFAULT_RECTIFY_DAYS = 3


# ---------------------------------------------------------------------------
# 发布
# ---------------------------------------------------------------------------

@transaction.atomic
def publish_task(*, title, building_id, area_id, period, scheduled_at, due_at,
                 checklist, publisher, code=None, assignee=None):
    try:
        building = Building.objects.get(pk=building_id)
    except Building.DoesNotExist:
        raise BusinessError('BUILDING_NOT_FOUND', 404)
    try:
        area = Area.objects.get(pk=area_id, building_id=building_id)
    except Area.DoesNotExist:
        raise BusinessError('AREA_NOT_FOUND', 404)

    task = InspectionTask.objects.create(
        code=code or _gen_task_code(),
        title=title,
        building=building,
        area=area,
        period=period,
        checklist=checklist or [],
        publisher=publisher,
        assignee=assignee,
        status=TASK_CLAIMED if assignee else TASK_PENDING,
        scheduled_at=scheduled_at,
        due_at=due_at,
        claimed_at=timezone.now() if assignee else None,
    )
    action = 'direct_assign' if assignee else 'publish'
    detail = f'发布巡检任务：{building.name}/{area.name}'
    if assignee:
        detail += f'，直接指派给{assignee.name}'
    record_history(
        StatusHistory.TARGET_TASK, task.id, action,
        to_status=task.status, actor=publisher, detail=detail,
    )
    return task


def _gen_task_code() -> str:
    return 'XJ' + timezone.now().strftime('%Y%m%d%H%M%S') + str(InspectionTask.objects.count() + 1001)


# ---------------------------------------------------------------------------
# 领取（并发安全）
# ---------------------------------------------------------------------------

@transaction.atomic
def claim_task(task_id, inspector):
    """条件更新：只有 assignee 为空且状态为待领取时才能领取成功。

    UPDATE ... WHERE assignee_id IS NULL AND status='pending' 是单条原子写
    语句：数据库行锁（PostgreSQL）或写事务排队（SQLite WAL）保证并发领取时
    只有一名巡检员更新成功（影响 1 行），其余返回 409。
    """
    updated = InspectionTask.objects.filter(
        pk=task_id, assignee__isnull=True, status=TASK_PENDING
    ).update(assignee=inspector, status=TASK_CLAIMED, claimed_at=timezone.now())

    if updated == 0:
        if not InspectionTask.objects.filter(pk=task_id).exists():
            raise BusinessError('TASK_NOT_FOUND', 404)
        raise BusinessError('TASK_NOT_CLAIMABLE', 409)

    task = InspectionTask.objects.get(pk=task_id)
    record_history(
        StatusHistory.TARGET_TASK, task.id, 'claim',
        from_status=TASK_PENDING, to_status=TASK_CLAIMED,
        actor=inspector, detail=f'{inspector.name}领取任务',
    )
    return task


# ---------------------------------------------------------------------------
# 提交现场结果（发现问题即生成整改单，保留来源）
# ---------------------------------------------------------------------------

@transaction.atomic
def submit_inspection(task_id, inspector, items, summary=''):
    task = InspectionTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise BusinessError('TASK_NOT_FOUND', 404)
    if task.assignee_id != inspector.id:
        raise BusinessError('NOT_TASK_OWNER', 403)
    if task.status != TASK_CLAIMED:
        raise BusinessError('TASK_NOT_SUBMITTABLE', 409, '当前任务状态不允许提交巡检结果（复验驳回后应由整改人重新整改）')

    normalized = _normalize_items(items, task.checklist)

    from_status = task.status
    submission = InspectionSubmission.objects.create(
        task=task, inspector=inspector, summary=summary or ''
    )
    issue_count = 0
    for item in normalized:
        saved = InspectionItemResult.objects.create(
            submission=submission,
            name=item['name'],
            result=item['result'],
            description=item.get('description', ''),
            photos=item.get('photos', []),
        )
        if item['result'] == RESULT_ISSUE:
            issue_count += 1
            _create_order_from_issue(task, saved, inspector, round_no=1)

    if issue_count:
        task.status = TASK_SUBMITTED
        action, to_status = 'submit_with_issue', TASK_SUBMITTED
        detail = f'提交巡检结果，发现 {issue_count} 项异常，已生成整改单'
    else:
        task.status = TASK_DONE
        task.closed_at = timezone.now()
        action, to_status = 'submit_normal_close', TASK_DONE
        detail = '提交巡检结果，全部正常，任务关闭'

    task.submitted_at = timezone.now()
    task.save()
    record_history(
        StatusHistory.TARGET_TASK, task.id, action,
        from_status=from_status, to_status=to_status,
        actor=inspector, detail=detail,
    )
    if issue_count == 0:
        from app.apps.escalation.services import resolve_open_for_target
        resolve_open_for_target('task', task.id)
    return task


def _normalize_items(items, checklist):
    if not items:
        raise BusinessError('VALIDATION_ERROR', 400, '至少提交一个检查项结果')
    names = [c if isinstance(c, str) else c.get('name') for c in checklist] if checklist else []
    normalized = []
    for raw in items:
        name = (raw.get('name') or '').strip()
        result = raw.get('result')
        if not name or result not in ('normal', 'issue'):
            raise BusinessError('VALIDATION_ERROR', 400, '检查项名称和结果(normal/issue)必填')
        if names and name not in names:
            raise BusinessError('VALIDATION_ERROR', 400, f'检查项「{name}」不在任务清单中')
        description = (raw.get('description') or '').strip()
        if result == RESULT_ISSUE and not description:
            raise BusinessError('ISSUE_NEEDS_DESCRIPTION', 400)
        normalized.append({
            'name': name,
            'result': result,
            'description': description,
            'photos': raw.get('photos') or [],
        })
    return normalized


def _create_order_from_issue(task, item_result, inspector, round_no):
    from app.apps.rectification.models import RectificationOrder as Order
    order = Order.objects.create(
        code=_gen_order_code(),
        task=task,
        source='inspection',
        source_item_name=item_result.name,
        issue_description=item_result.description,
        issue_photos=item_result.photos,
        severity='medium',
        status='pending',
        round=round_no,
        due_at=timezone.now() + timedelta(days=DEFAULT_RECTIFY_DAYS),
    )
    record_history(
        StatusHistory.TARGET_ORDER, order.id, 'create_from_inspection',
        to_status='pending', actor=inspector,
        detail=f'巡检异常「{item_result.name}」生成整改单，问题：{item_result.description}',
    )
    return order


def _gen_order_code() -> str:
    return 'ZG' + timezone.now().strftime('%Y%m%d%H%M%S') + str(RectificationOrder.objects.count() + 2001)


# ---------------------------------------------------------------------------
# 任务关闭（全部整改单复验通过后）
# ---------------------------------------------------------------------------

@transaction.atomic
def close_task(task_id, inspector):
    task = InspectionTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise BusinessError('TASK_NOT_FOUND', 404)
    if task.assignee_id != inspector.id:
        raise BusinessError('NOT_TASK_OWNER', 403)

    open_orders = task.rectification_orders.exclude(status__in=('verified', 'closed'))
    if open_orders.exists():
        raise BusinessError('TASK_HAS_OPEN_ORDERS', 409)

    from_status = task.status
    task.status = TASK_DONE
    task.closed_at = timezone.now()
    task.save()

    # 复验通过的整改单同步关闭
    for order in task.rectification_orders.filter(status='verified'):
        order.status = 'closed'
        order.closed_at = timezone.now()
        order.save(update_fields=['status', 'closed_at', 'updated_at'])
        record_history(
            StatusHistory.TARGET_ORDER, order.id, 'close_with_task',
            from_status='verified', to_status='closed',
            actor=inspector, detail='随巡检任务关闭',
        )

    record_history(
        StatusHistory.TARGET_TASK, task.id, 'close',
        from_status=from_status, to_status=TASK_DONE,
        actor=inspector, detail='所有整改单复验通过，任务闭环关闭',
    )
    from app.apps.escalation.services import resolve_open_for_target
    resolve_open_for_target('task', task.id)
    for closed_order in task.rectification_orders.filter(status='closed'):
        resolve_open_for_target('rectification_order', closed_order.id)
    return task


# ---------------------------------------------------------------------------
# 改期 / 重新分派（物业操作，同步待办归属、期限与历史）
# ---------------------------------------------------------------------------

@transaction.atomic
def reschedule_task(task_id, manager, scheduled_at, due_at):
    task = InspectionTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise BusinessError('TASK_NOT_FOUND', 404)
    if task.status == TASK_DONE:
        raise BusinessError('TASK_NOT_RESCHEDULABLE', 409)

    old_scheduled, old_due = task.scheduled_at, task.due_at
    task.scheduled_at = scheduled_at
    task.due_at = due_at
    task.save(update_fields=['scheduled_at', 'due_at', 'updated_at'])
    record_history(
        StatusHistory.TARGET_TASK, task.id, 'reschedule',
        from_status=task.status, to_status=task.status, actor=manager,
        detail=f'改期：计划 {old_scheduled:%Y-%m-%d %H:%M} → {scheduled_at:%Y-%m-%d %H:%M}，'
               f'期限 {old_due:%Y-%m-%d %H:%M} → {due_at:%Y-%m-%d %H:%M}',
    )
    return task


@transaction.atomic
def reassign_task(task_id, manager, new_inspector):
    if new_inspector.role != 'inspector' or not new_inspector.is_active:
        raise BusinessError('ROLE_MISMATCH', 400, '只能重新分派给启用中的巡检员')
    task = InspectionTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise BusinessError('TASK_NOT_FOUND', 404)
    if task.status == TASK_DONE:
        raise BusinessError('TASK_NOT_REASSIGNABLE', 409)

    old_assignee = task.assignee
    old_status = task.status
    # 归属切换：无论原来是否已领取，新负责人到位即为其待办，原负责人立即失效
    task.assignee = new_inspector
    if task.status == TASK_PENDING:
        task.status = TASK_CLAIMED
        task.claimed_at = timezone.now()
    task.save()

    old_name = old_assignee.name if old_assignee else '公共池'
    record_history(
        StatusHistory.TARGET_TASK, task.id, 'reassign',
        from_status=old_status, to_status=task.status, actor=manager,
        detail=f'重新分派：{old_name} → {new_inspector.name}，待办归属同步更新',
    )
    return task


@transaction.atomic
def release_task(task_id, manager):
    """将任务退回公共池（例如原负责人长期未处理），状态回到待领取。"""
    task = InspectionTask.objects.select_for_update().filter(pk=task_id).first()
    if task is None:
        raise BusinessError('TASK_NOT_FOUND', 404)
    if task.status == TASK_DONE:
        raise BusinessError('TASK_NOT_REASSIGNABLE', 409)
    old_assignee = task.assignee
    old_status = task.status
    task.assignee = None
    task.status = TASK_PENDING
    task.claimed_at = None
    task.save()
    record_history(
        StatusHistory.TARGET_TASK, task.id, 'release_to_pool',
        from_status=old_status, to_status=TASK_PENDING, actor=manager,
        detail=f'{old_assignee.name if old_assignee else "公共池"} 的任务退回公共待领池',
    )
    return task
