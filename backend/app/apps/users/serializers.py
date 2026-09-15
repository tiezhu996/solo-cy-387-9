from rest_framework import serializers

from .models import AuthToken, User


class UserSerializer(serializers.ModelSerializer):
    roleLabel = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'role', 'roleLabel', 'phone', 'is_active']


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def create(self, validated):
        user = User.objects.filter(username=validated['username']).first()
        if user is None or not user.check_password(validated['password']):
            from app.constants.errors import BusinessError
            raise BusinessError('UNAUTHORIZED', 401, '用户名或密码错误')
        if not user.is_active:
            from app.constants.errors import BusinessError
            raise BusinessError('USER_DISABLED', 403)
        token = AuthToken.issue(user)
        return token


class UserManageSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'name', 'role', 'phone', 'is_active', 'password']

    def create(self, validated):
        password = validated.pop('password', None) or '123456'
        user = User(**validated)
        user.set_password(password)
        user.save()
        return user
