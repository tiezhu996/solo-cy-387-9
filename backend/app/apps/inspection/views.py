"""巡检任务 API：发布、领取、提交、复验后关闭、改期、重新分派、时间线。"""

from django.db.models import Count, Q
from rest_framework.views import APIView

from app.apps.audit.models import StatusHistory
from app.apps.users.models import User
from app.constants.errors import BusinessError
from app.constants.enums import ROLE_INSPECTOR, ROLE_PROPERTY
from app.utils.permissions import (
    ActiveUserPermission,
    IsInspector,
    IsProperty,
)
from app.utils.response import ok
from . import services
from .models import InspectionTask
from .serializers import (
    RescheduleSerializer,
    SubmitInspectionSerializer,
    TaskDetailSerializer,
    TaskListSerializer,
    TaskPublishSerializer,
)


def _base_queryset():
    return InspectionTask.objects.select_related(
        'building', 'area', 'assignee', 'publisher'
    ).annotate(
        open_order_count=Count(
            'rectification_orders',
            filter=~Q(rectification_orders__status__in=['verified', 'closed']),
        )
    )


class TaskListCreateView(APIView):
    def get_permissions(self):
        return [IsProperty()] if self.request.method == 'POST' else [ActiveUserPermission()]

    def get(self, request):
        tasks = _base_queryset()
        status = request.query_params.get('status')
        if status:
            tasks = tasks.filter(status=status)
        scope = request.query_params.get('scope')
        if scope == 'mine':
            tasks = tasks.filter(assignee=request.user)
        elif scope == 'pool':
            # 公共池：无归属且未关闭。含待领取(pending)及停用交接后等待接管复验(submitted/returned)
            tasks = tasks.filter(
                assignee__isnull=True, status__in=['pending', 'submitted', 'returned']
            )
        building_id = request.query_params.get('building')
        if building_id:
            tasks = tasks.filter(building_id=building_id)
        return ok(TaskListSerializer(tasks, many=True).data)

    def post(self, request):
        serializer = TaskPublishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        assignee = None
        if data.get('assignee_id'):
            assignee = User.objects.filter(pk=data['assignee_id']).first()
            if assignee is None or assignee.role != ROLE_INSPECTOR or not assignee.is_active:
                raise BusinessError('ROLE_MISMATCH', 400, '只能指派给启用中的巡检员')
        task = services.publish_task(
            title=data['title'], building_id=data['building_id'], area_id=data['area_id'],
            period=data['period'], scheduled_at=data['scheduled_at'], due_at=data['due_at'],
            checklist=data['checklist'], publisher=request.user, assignee=assignee,
        )
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data, status_code=201)


class TaskDetailView(APIView):
    permission_classes = [ActiveUserPermission]

    def get(self, request, task_id):
        task = _base_queryset().filter(pk=task_id).first()
        if task is None:
            raise BusinessError('TASK_NOT_FOUND', 404)
        return ok(TaskDetailSerializer(task).data)


class _TaskActionView(APIView):
    permission_classes = [ActiveUserPermission]

    def get_task_or_404(self, task_id):
        task = InspectionTask.objects.filter(pk=task_id).first()
        if task is None:
            raise BusinessError('TASK_NOT_FOUND', 404)
        return task


class TaskClaimView(_TaskActionView):
    permission_classes = [IsInspector]

    def post(self, request, task_id):
        task = services.claim_task(task_id, request.user)
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data)


class TaskSubmitView(_TaskActionView):
    permission_classes = [IsInspector]

    def post(self, request, task_id):
        serializer = SubmitInspectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = services.submit_inspection(
            task_id, request.user, serializer.validated_data['items'],
            serializer.validated_data.get('summary', ''),
        )
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data)


class TaskCloseView(_TaskActionView):
    permission_classes = [IsInspector]

    def post(self, request, task_id):
        task = services.close_task(task_id, request.user)
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data)


class TaskRescheduleView(_TaskActionView):
    permission_classes = [IsProperty]

    def post(self, request, task_id):
        self.get_task_or_404(task_id)
        serializer = RescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = services.reschedule_task(
            task_id, request.user,
            serializer.validated_data['scheduled_at'], serializer.validated_data['due_at'],
        )
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data)


class TaskReassignView(_TaskActionView):
    permission_classes = [IsProperty]

    def post(self, request, task_id):
        self.get_task_or_404(task_id)
        data = request.data
        if data.get('to_pool'):
            task = services.release_task(task_id, request.user)
        else:
            new_inspector = User.objects.filter(pk=data.get('user_id')).first()
            if new_inspector is None:
                raise BusinessError('USER_NOT_FOUND', 404)
            task = services.reassign_task(task_id, request.user, new_inspector)
        return ok(TaskDetailSerializer(_base_queryset().get(pk=task.id)).data)


ACTION_LABELS = {
    'publish': '发布任务', 'direct_assign': '发布并直接指派', 'claim': '领取任务',
    'submit_with_issue': '提交巡检（发现异常）', 'submit_normal_close': '提交巡检（正常关闭）',
    'close': '闭环关闭', 'reschedule': '任务改期', 'reassign': '重新分派',
    'release_to_pool': '退回公共池', 'recheck_reject': '复验驳回',
    'handoff_user': '停用并交接给接管人', 'handoff_pool': '停用并退回公共池',
    'all_verified': '全部复验通过', 'escalate': '超期升级',
    'escalation_resolved': '挂起升级单解除',
    'create_from_inspection': '巡检异常生成整改单', 'claim_order': '领取整改单',
    'submit_resolution': '提交整改结果', 'recheck_pass': '复验通过',
    'recheck_reject_order': '复验驳回', 'close_with_task': '随任务关闭',
    'order_reassign': '重新分派整改单', 'order_escalate': '整改超期升级',
}


class TaskTimelineView(_TaskActionView):
    """任务与其名下所有整改单的完整流转时间线（刷新后仍可完整回放）。"""

    def get(self, request, task_id):
        task = self.get_task_or_404(task_id)
        order_ids = list(task.rectification_orders.values_list('id', flat=True))
        entries = list(
            StatusHistory.objects.filter(
                target_type=StatusHistory.TARGET_TASK, target_id=task.id
            ).values('id', 'action', 'from_status', 'to_status', 'actor_name', 'detail', 'created_at')
        )
        order_entries = list(
            StatusHistory.objects.filter(
                target_type=StatusHistory.TARGET_ORDER, target_id__in=order_ids
            ).values('id', 'action', 'from_status', 'to_status', 'actor_name',
                     'detail', 'created_at', 'target_id')
        )
        order_codes = {o.id: o.code for o in task.rectification_orders.all()}
        for e in order_entries:
            e['target_type'] = 'rectification_order'
            e['target_code'] = order_codes.get(e['target_id'], '')
            e['action_label'] = ACTION_LABELS.get(e['action'], e['action'])
        for e in entries:
            e['target_type'] = 'task'
            e['target_code'] = task.code
            e['target_id'] = task.id
            e['action_label'] = ACTION_LABELS.get(e['action'], e['action'])
        timeline = sorted(entries + order_entries, key=lambda x: (x['created_at'], x['id']))
        return ok(timeline)
