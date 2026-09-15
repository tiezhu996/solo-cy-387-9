import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-patrolloop-secret')
DEBUG = os.getenv('DJANGO_DEBUG', 'true').lower() == 'true'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'rest_framework',
    'app.apps.users.apps.UsersConfig',
    'app.apps.organization.apps.OrganizationConfig',
    'app.apps.audit.apps.AuditConfig',
    'app.apps.inspection.apps.InspectionConfig',
    'app.apps.rectification.apps.RectificationConfig',
    'app.apps.escalation.apps.EscalationConfig',
]

MIDDLEWARE = [
    'django.middleware.common.CommonMiddleware',
    'app.middleware.request_log.RequestLogMiddleware',
]

ROOT_URLCONF = 'app.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {'context_processors': []},
    }
]

DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
        conn_max_age=60,
    )
}

# 本地 SQLite 开启 WAL 与忙等待：并发写时排队重试，而不是直接 "database is locked"。
# 生产使用 PostgreSQL，行级锁由 select_for_update 保证。
if DATABASES['default']['ENGINE'] == 'django.db.backends.sqlite3':
    from django.db.backends.signals import connection_created

    def _sqlite_pragma(sender, connection, **kwargs):
        if connection.vendor == 'sqlite':
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL;')
            cursor.execute('PRAGMA busy_timeout=20000;')
            cursor.execute('PRAGMA synchronous=NORMAL;')

    connection_created.connect(_sqlite_pragma)
    DATABASES['default'].setdefault('OPTIONS', {})['timeout'] = 20

AUTH_USER_MODEL = 'users.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', BASE_DIR / 'media'))
MEDIA_URL = '/media/'

USE_TZ = True
TIME_ZONE = 'Asia/Shanghai'

# 超期升级阈值（小时）：巡检领取后 / 整改单生成后未处理
INSPECTION_OVERDUE_HOURS = int(os.getenv('INSPECTION_OVERDUE_HOURS', '48'))
RECTIFICATION_OVERDUE_HOURS = int(os.getenv('RECTIFICATION_OVERDUE_HOURS', '72'))

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'app.utils.authentication.SimpleTokenAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAuthenticated',),
    'EXCEPTION_HANDLER': 'app.utils.exception_handler.standard_exception_handler',
    'UNAUTHENTICATED_USER': None,
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {'format': '[%(asctime)s] %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {'console': {'class': 'logging.StreamHandler', 'formatter': 'standard'}},
    'root': {'handlers': ['console'], 'level': 'INFO'},
}
