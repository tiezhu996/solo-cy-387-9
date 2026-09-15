"""人员停用与待办交接。

停用巡检员/整改人时，必须在同一事务内把其名下未完成待办交给指定接管人或退回
公共池，否则待办会挂在停用账号名下形成死信。

并发安全：事务第一条语句就是对用户行的条件更新（is_active 1→0），并发停用
只有一人影响 1 行；拿到写锁后再批量交接任务/整改单。领取侧同样以条件更新
抢锁，因此「停用 vs 停用」「停用 vs 领取」都只有一个结果，失败方整体回滚、
不改任何数据。原处理记录与状态历史只增不改；重新启用不自动拿回已释放待办。
"""

from django.db import transaction
from django.db.models import Case, CharField, DateTimeField, F, Q, Value, When
from django.utils import timezone

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.apps.escalation.services import resolve_open_for_target
from app.apps.inspection.models import InspectionTask
from app.apps.rectification.models import RectificationOrder
from app.apps.users.models import User
from app.constants.errors import BusinessError


@transaction.atomic
def deactivate_and_handoff(user_id, manager, takeover_user_id=None):
    """停用人员并交接其在办待办。

    takeover_user_id 为空：在办任务/整改单退回公共池，可被重新领取。
    takeover_user_id 非空：直接归属接管人（须同角色、启用中、非本人）。

    状态映射（不丢进度、不重复走流程）：
    - 巡检任务：pending 随接管转 claimed；退回池时 pending/claimed 重置为
      pending，submitted/returned 保持原状，供新巡检员领取后接管复验。
    - 整改单：pending 随接管转 processing；退回池时 pending/processing/returned
      重置为 pending 供重新领取整改，submitted 保持原状由任务接管人复验。
    """
    now = timezone.now()

    # —— 第一步即写：条件更新抢占用户行，并发停用只有一人成功并立刻持有写锁 ——
    flipped = User.objects.filter(pk=user_id, is_active=True).update(is_active=False)
    if flipped == 0:
        if not User.objects.filter(pk=user_id).exists():
            raise BusinessError('USER_NOT_FOUND', 404)
        # 已是停用态：幂等返回，不重复交接
        user = User.objects.get(pk=user_id)
        return {'user': user, 'takeover': None, 'task_count': 0,
                'order_count': 0, 'changed': False}

    user = User.objects.get(pk=user_id)

    takeover = None
    if takeover_user_id:
        if int(takeover_user_id) == user.id:
            raise BusinessError('ROLE_MISMATCH', 400, '接管人不能是被停用人员本人')
        takeover = User.objects.select_for_update().filter(pk=takeover_user_id).first()
        if takeover is None:
            raise BusinessError('USER_NOT_FOUND', 404)
        if not takeover.is_active:
            raise BusinessError('USER_DISABLED', 400, '接管人处于停用状态，无法接管')
        if takeover.role != user.role:
            raise BusinessError('ROLE_MISMATCH', 400, '接管人角色与被停用人员不一致')

    task_count = _handoff_tasks(user, takeover, manager, now)
    order_count = _handoff_orders(user, takeover, manager, now)

    where = f'；交接巡检任务 {task_count} 个、整改单 {order_count} 张'
    where += f'，接管人：{takeover.name}' if takeover else '，均已退回公共待领池'
    record_history(
        'user', user.id, 'user_disable', actor=manager,
        detail=f'{user.name} 账号已停用{where}',
    )

    return {'user': user, 'takeover': takeover, 'task_count': task_count,
            'order_count': order_count, 'changed': True}


def _handoff_tasks(user, takeover, manager, now):
    # 先取明细（此时本事务已持写锁，读取安全），用于写历史
    tasks = list(
        InspectionTask.objects.filter(assignee=user).exclude(status='done').order_by('id')
    )
    if not tasks:
        return 0
    qs = InspectionTask.objects.filter(assignee=user).exclude(status='done')

    if takeover is not None:
        qs.update(
            assignee=takeover,
            claimed_at=Case(
                When(status='pending', then=Value(now)),
                default=F('claimed_at'),
                output_field=DateTimeField(),
            ),
            status=Case(
                When(status='pending', then=Value('claimed')),
                default=F('status'),
                output_field=CharField(),
            ),
        )
    else:
        qs.update(
            assignee=None,
            claimed_at=Case(
                When(status__in=['pending', 'claimed'], then=Value(None)),
                default=F('claimed_at'),
                output_field=DateTimeField(),
            ),
            status=Case(
                When(status__in=['pending', 'claimed'], then=Value('pending')),
                default=F('status'),
                output_field=CharField(),
            ),
        )

    for task in tasks:
        if takeover is not None:
            action, detail = 'handoff_user', (
                f'原巡检员{user.name}停用，任务交接给{takeover.name}接管，'
                f'巡检期限保持 {timezone.localtime(task.due_at):%Y-%m-%d %H:%M}'
            )
        else:
            action, detail = 'handoff_pool', (
                f'原巡检员{user.name}停用，任务退回公共待领池，'
                f'巡检期限保持 {timezone.localtime(task.due_at):%Y-%m-%d %H:%M}'
            )
        # 历史中的 to_status 需与更新后的实际状态一致
        new_status = task.status
        if takeover is not None and new_status == 'pending':
            new_status = 'claimed'
        if takeover is None and new_status in ('pending', 'claimed'):
            new_status = 'pending'
        record_history(
            StatusHistory.TARGET_TASK, task.id, action,
            from_status=task.status, to_status=new_status, actor=manager, detail=detail,
        )
        resolve_open_for_target('task', task.id, actor=manager, note=detail)
    return len(tasks)


def _handoff_orders(user, takeover, manager, now):
    orders = list(
        RectificationOrder.objects.filter(assignee=user)
        .exclude(status__in=['verified', 'closed']).order_by('id')
    )
    if not orders:
        return 0
    qs = (
        RectificationOrder.objects.filter(assignee=user)
        .exclude(status__in=['verified', 'closed'])
    )

    if takeover is not None:
        qs.update(
            assignee=takeover,
            claimed_at=Case(
                When(status='pending', then=Value(now)),
                default=F('claimed_at'),
                output_field=DateTimeField(),
            ),
            status=Case(
                When(status='pending', then=Value('processing')),
                default=F('status'),
                output_field=CharField(),
            ),
        )
    else:
        qs.update(
            assignee=None,
            claimed_at=Case(
                When(status__in=['pending', 'processing', 'returned'], then=Value(None)),
                default=F('claimed_at'),
                output_field=DateTimeField(),
            ),
            status=Case(
                When(status__in=['pending', 'processing', 'returned'], then=Value('pending')),
                default=F('status'),
                output_field=CharField(),
            ),
        )

    for order in orders:
        if takeover is not None:
            action, detail = 'handoff_user', (
                f'原整改人{user.name}停用，整改单交接给{takeover.name}接管，'
                f'整改期限保持 {timezone.localtime(order.due_at):%Y-%m-%d %H:%M}'
            )
        else:
            action, detail = 'handoff_pool', (
                f'原整改人{user.name}停用，整改单退回公共待领池，'
                f'整改期限保持 {timezone.localtime(order.due_at):%Y-%m-%d %H:%M}'
            )
        new_status = order.status
        if takeover is not None and new_status == 'pending':
            new_status = 'processing'
        if takeover is None and new_status in ('pending', 'processing', 'returned'):
            new_status = 'pending'
        record_history(
            StatusHistory.TARGET_ORDER, order.id, action,
            from_status=order.status, to_status=new_status, actor=manager, detail=detail,
        )
        resolve_open_for_target('rectification_order', order.id, actor=manager, note=detail)
    return len(orders)
