"""超期升级服务：扫描超期的巡检任务与整改单，生成升级单推送给主管。"""

from django.db import transaction
from django.utils import timezone

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.constants.enums import ORDER_RETURNED, TASK_RETURNED
from .models import Escalation

# 视为超期的状态
OVERDUE_TASK_STATUSES = ('pending', 'claimed', 'submitted', TASK_RETURNED)
OVERDUE_ORDER_STATUSES = ('pending', 'processing', ORDER_RETURNED)


def has_open_escalation(target_type, target_id):
    return Escalation.objects.filter(
        target_type=target_type, target_id=target_id, status=Escalation.STATUS_OPEN
    ).exists()


@transaction.atomic
def scan_overdue(now=None):
    """扫描并生成升级单。幂等：同一对象存在未处置升级单时不重复生成。"""
    from app.apps.inspection.models import InspectionTask
    from app.apps.rectification.models import RectificationOrder

    now = now or timezone.now()
    created = []

    overdue_tasks = InspectionTask.objects.filter(
        status__in=OVERDUE_TASK_STATUSES, due_at__lt=now
    ).select_for_update(skip_locked=True)
    for task in overdue_tasks:
        if has_open_escalation('task', task.id):
            continue
        esc = Escalation.objects.create(
            target_type='task', target_id=task.id,
            reason=f'巡检任务 {task.code} 已于 {task.due_at:%Y-%m-%d %H:%M} 超期未闭环',
            overdue_at=task.due_at,
        )
        record_history(
            StatusHistory.TARGET_TASK, task.id, 'escalate',
            from_status=task.status, to_status=task.status,
            detail='超期未处理，自动升级给主管',
        )
        created.append(esc)

    overdue_orders = RectificationOrder.objects.filter(
        status__in=OVERDUE_ORDER_STATUSES, due_at__lt=now
    ).select_for_update(skip_locked=True)
    for order in overdue_orders:
        if has_open_escalation('rectification_order', order.id):
            continue
        esc = Escalation.objects.create(
            target_type='rectification_order', target_id=order.id,
            reason=f'整改单 {order.code} 已于 {order.due_at:%Y-%m-%d %H:%M} 超期未处理',
            overdue_at=order.due_at,
        )
        record_history(
            StatusHistory.TARGET_ORDER, order.id, 'escalate',
            from_status=order.status, to_status=order.status,
            detail='整改超期，自动升级给主管',
        )
        created.append(esc)

    return created


@transaction.atomic
def resolve_escalation(escalation_id, supervisor, note):
    esc = Escalation.objects.select_for_update().filter(pk=escalation_id).first()
    if esc is None:
        from app.constants.errors import BusinessError
        raise BusinessError('VALIDATION', 404, '升级单不存在')
    esc.status = Escalation.STATUS_RESOLVED
    esc.supervisor = supervisor
    esc.handle_note = note or ''
    esc.resolved_at = timezone.now()
    esc.save()
    record_history(
        esc.target_type, esc.target_id, 'escalation_resolved',
        actor=supervisor, detail=f'主管处置升级单：{note or "已处理"}',
    )
    return esc


def resolve_open_for_target(target_type, target_id):
    """对象已完成闭环时，自动关闭其挂起的升级单。"""
    return Escalation.objects.filter(
        target_type=target_type, target_id=target_id, status=Escalation.STATUS_OPEN
    ).update(status=Escalation.STATUS_RESOLVED, handle_note='对象已完成闭环，自动解除',
             resolved_at=timezone.now())
