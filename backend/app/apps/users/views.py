"""登录与当前用户。"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from app.constants.errors import BusinessError
from app.utils.response import ok
from .models import User
from .serializers import LoginSerializer, UserSerializer


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save()
        return ok({'token': token.key, 'user': UserSerializer(token.user).data})


class LogoutView(APIView):
    def post(self, request):
        auth = request.auth
        if auth is not None:
            auth.delete()
        return ok({'loggedOut': True})


class MeView(APIView):
    def get(self, request):
        return ok(UserSerializer(request.user).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def demo_accounts(request):
    """演示账号清单，前端登录页展示用。"""
    accounts = User.objects.filter(is_active=True).order_by('role', 'id')
    return ok(UserSerializer(accounts, many=True).data)
