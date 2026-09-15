from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models

from app.constants.enums import ROLE_CHOICES, ROLE_INSPECTOR
import secrets


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra):
        if not username:
            raise ValueError('用户名必填')
        user = self.model(username=username, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra):
        extra.setdefault('role', 'property')
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra)


class User(AbstractBaseUser):
    """平台账号：物业管理员 / 巡检员 / 整改人 / 主管。"""

    username = models.CharField('登录名', max_length=40, unique=True)
    name = models.CharField('姓名', max_length=40)
    role = models.CharField('角色', max_length=20, choices=ROLE_CHOICES, default=ROLE_INSPECTOR)
    phone = models.CharField('联系电话', max_length=20, blank=True, default='')
    is_active = models.BooleanField('启用状态', default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['name', 'role']

    class Meta:
        db_table = 'users_user'
        ordering = ['id']

    def __str__(self):
        return f'{self.name}({self.username})'


class AuthToken(models.Model):
    """登录令牌：持久化在数据库中，浏览器刷新或服务重启后登录态仍然有效。"""

    key = models.CharField('令牌', max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        User, verbose_name='所属用户', related_name='auth_tokens', on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users_auth_token'

    @classmethod
    def issue(cls, user) -> 'AuthToken':
        return cls.objects.create(key=secrets.token_hex(24), user=user)

    def __str__(self):
        return self.key
