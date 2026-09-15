"""物业对人员的管理：列表、新增、停用/启用。停用后其待办需由物业重新分派。"""

from rest_framework.views import APIView

from app.apps.audit.models import StatusHistory
from app.apps.audit.services import record_history
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
    """启用/停用人员；停用不删除任何历史记录，仅使其无法再登录与被分派。"""

    permission_classes = [IsProperty]

    def post(self, request, user_id):
        user = User.objects.filter(pk=user_id).first()
        if user is None:
            raise BusinessError('USER_NOT_FOUND', 404)
        active = bool(request.data.get('is_active'))
        if user.is_active == active:
            return ok(UserSerializer(user).data)
        user.is_active = active
        user.save(update_fields=['is_active'])
        action = 'user_enable' if active else 'user_disable'
        record_history(
            'user', user.id, action, actor=request.user,
            detail=f'{user.name} 账号已{"启用" if active else "停用"}',
        )
        return ok(UserSerializer(user).data)
