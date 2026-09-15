"""DRF 权限：按角色控制访问，并拒绝已停用账号。"""

from rest_framework.permissions import BasePermission, IsAuthenticated

from app.constants.errors import BusinessError
from app.constants.enums import (
    ROLE_INSPECTOR,
    ROLE_PROPERTY,
    ROLE_RECTIFIER,
    ROLE_SUPERVISOR,
)


class ActiveUserPermission(IsAuthenticated):
    """已认证且账号处于启用状态。"""

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if not request.user.is_active:
            raise BusinessError('USER_DISABLED', status_code=403)
        return True


class _RolePermission(ActiveUserPermission):
    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.user.role not in self.allowed_roles:
            raise BusinessError('PERMISSION_DENIED', status_code=403)
        return True


class IsProperty(_RolePermission):
    allowed_roles = (ROLE_PROPERTY,)


class IsInspector(_RolePermission):
    allowed_roles = (ROLE_INSPECTOR,)


class IsRectifier(_RolePermission):
    allowed_roles = (ROLE_RECTIFIER,)


class IsSupervisor(_RolePermission):
    allowed_roles = (ROLE_SUPERVISOR,)


class IsPropertyOrSupervisor(_RolePermission):
    allowed_roles = (ROLE_PROPERTY, ROLE_SUPERVISOR)
