"""整改单 API：领取、提交处理结果、复验、关闭、重新分派。"""

from rest_framework.views import APIView

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.apps.users.models import User
from app.constants.enums import (
    ORDER_CLOSED,
    ORDER_VERIFIED,
    ROLE_PROPERTY,
    ROLE_RECTIFIER,
    TASK_DONE,
)
from app.constants.errors import BusinessError
from app.utils.permissions import (
    ActiveUserPermission,
    IsInspector,
    IsProperty,
    IsRectifier,
)
from app.utils.response import ok
from . import services
from .models import RectificationOrder
from .serializers import (
    OrderDetailSerializer,
    OrderListSerializer,
    ReassignOrderSerializer,
    RecheckSerializer,
    SubmitResolutionSerializer,
)


def _qs():
    return RectificationOrder.objects.select_related('assignee', 'task')


class OrderListView(APIView):
    permission_classes = [ActiveUserPermission]

    def get(self, request):
        orders = _qs()
        status = request.query_params.get('status')
        if status:
            orders = orders.filter(status=status)
        scope = request.query_params.get('scope')
        if scope == 'mine':
            orders = orders.filter(assignee=request.user)
        elif scope == 'mine_all':
            orders = orders.filter(assignee=request.user)
        elif scope == 'pool':
            orders = orders.filter(assignee__isnull=True, status='pending')
        task_id = request.query_params.get('task')
        if task_id:
            orders = orders.filter(task_id=task_id)
        return ok(OrderListSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    permission_classes = [ActiveUserPermission]

    def get(self, request, order_id):
        order = _qs().filter(pk=order_id).first()
        if order is None:
            raise BusinessError('ORDER_NOT_FOUND', 404)
        return ok(OrderDetailSerializer(order).data)


class OrderClaimView(APIView):
    permission_classes = [IsRectifier]

    def post(self, request, order_id):
        order = services.claim_order(order_id, request.user)
        return ok(OrderDetailSerializer(_qs().get(pk=order.id)).data)


class OrderSubmitView(APIView):
    permission_classes = [IsRectifier]

    def post(self, request, order_id):
        serializer = SubmitResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.submit_resolution(
            order_id, request.user,
            serializer.validated_data['note'], serializer.validated_data.get('photos', []),
        )
        return ok(OrderDetailSerializer(_qs().get(pk=order.id)).data)


class OrderRecheckView(APIView):
    permission_classes = [IsInspector]

    def post(self, request, order_id):
        serializer = RecheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = services.recheck_order(
            order_id, request.user, serializer.validated_data['passed'],
            serializer.validated_data.get('note', ''),
        )
        return ok(OrderDetailSerializer(_qs().get(pk=order.id)).data)


class OrderCloseView(APIView):
    """整改单单独关闭入口：复验通过后，由任务巡检员确认关闭。"""

    permission_classes = [IsInspector]

    def post(self, request, order_id):
        order = RectificationOrder.objects.select_related('task').filter(pk=order_id).first()
        if order is None:
            raise BusinessError('ORDER_NOT_FOUND', 404)
        if order.status != ORDER_VERIFIED:
            raise BusinessError('ORDER_NOT_RECHECKABLE', 409, '整改单复验通过后才能关闭')
        if order.task.assignee_id != request.user.id:
            raise BusinessError('NOT_TASK_OWNER', 403)
        from django.utils import timezone
        order.status = ORDER_CLOSED
        order.closed_at = timezone.now()
        order.save(update_fields=['status', 'closed_at', 'updated_at'])
        record_history(
            StatusHistory.TARGET_ORDER, order.id, 'close_with_task',
            from_status=ORDER_VERIFIED, to_status=ORDER_CLOSED, actor=request.user,
            detail='复验通过后关闭整改单',
        )
        from app.apps.escalation.services import resolve_open_for_target
        resolve_open_for_target('rectification_order', order.id)
        return ok(OrderDetailSerializer(_qs().get(pk=order.id)).data)


class OrderReassignView(APIView):
    permission_classes = [IsProperty]

    def post(self, request, order_id):
        serializer = ReassignOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_rectifier = User.objects.filter(pk=serializer.validated_data['user_id']).first()
        if new_rectifier is None:
            raise BusinessError('USER_NOT_FOUND', 404)
        order = services.reassign_order(order_id, request.user, new_rectifier)
        return ok(OrderDetailSerializer(_qs().get(pk=order.id)).data)
