"""超期扫描定时命令：可由 cron / k8s CronJob 周期调用。

    python manage.py scan_overdue
"""

from django.core.management.base import BaseCommand

from app.apps.escalation.services import scan_overdue
from app.utils.logger import get_logger

logger = get_logger('command.scan_overdue')


class Command(BaseCommand):
    help = '扫描超期未处理的巡检任务与整改单，生成升级单推送给主管'

    def handle(self, *args, **options):
        created = scan_overdue()
        logger.info('超期扫描完成，新增升级单 %d 条', len(created))
        self.stdout.write(f'created escalations: {len(created)}')
