"""物业对人员的管理：列表、新增、停用/启用。

停用会在同一事务内交接在办待办（见 users.handoff）；启用只恢复账号，
不会自动拿回此前释放的待办，历史记录也始终保留。
"""

from rest_framework.views import APIView

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
from app.apps.users.handoff import deactivate_and_handoff
from app.constants.errors import BusinessError
from app.utils.permissions import IsProperty
from app.utils.response import ok
from .models import User
from .serializers import UserManageSerializer, UserSerializer


class UserListView(APIView):
    permission_classes = [IsProperty]

    def get(self, request):
        role = request.query_params.get('role')
        users = User.objects.all().order_by('role', 'id')
        if role:
            users = users.filter(role=role)
        return ok(UserSerializer(users, many=True).data)

    def post(self, request):
        serializer = UserManageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return ok(UserSerializer(user).data, status_code=201)


class UserActiveView(APIView):
    """启用/停用人员。停用必须连带交接待办，不删除任何历史记录。"""

    permission_classes = [IsProperty]

    def post(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise BusinessError('USER_NOT_FOUND', 404)

        active = bool(request.data.get('is_active'))

        if active:
            # 启用仅恢复登录资格，不自动拿回已释放待办
            if user.is_active:
                return ok(UserSerializer(user).data)
            user.is_active = True
            user.save(update_fields=['is_active'])
            record_history(
                'user', user.id, 'user_enable', actor=request.user,
                detail=f'{user.name} 账号已启用（不自动恢复此前待办）',
            )
            return ok(UserSerializer(user).data)

        # 停用：事务内交接全部在办待办
        takeover_user_id = request.data.get('takeover_user_id')
        result = deactivate_and_handoff(
            user_id, request.user,
            takeover_user_id=takeover_user_id if takeover_user_id else None,
        )
        data = UserSerializer(result['user']).data
        data['handoff'] = {
            'task_count': result['task_count'],
            'order_count': result['order_count'],
            'takeover': result['takeover'].name if result['takeover'] else None,
        }
        return ok(data)
