"""基于数据库持久化 Token 的认证，Authorization: Token <key>。"""

from rest_framework.authentication import BaseAuthentication

from app.apps.users.models import AuthToken
from app.constants.errors import BusinessError


class SimpleTokenAuthentication(BaseAuthentication):
    keyword = 'Token'

    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        try:
            token = AuthToken.objects.select_related('user').get(key=parts[1])
        except AuthToken.DoesNotExist:
            raise BusinessError('UNAUTHORIZED', status_code=401)
        if not token.user.is_active:
            raise BusinessError('USER_DISABLED', status_code=403)
        return token.user, token
