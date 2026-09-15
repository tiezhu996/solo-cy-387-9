from django.db import models

from app.constants.enums import (
    ESCALATION_SUPERVISOR,
    ESCALATION_CHOICES,
    TARGET_CHOICES,
    TARGET_TASK,
)


class Escalation(models.Model):
    """超期升级单：任务或整改单超期未处理时自动生成，推送给主管处置。"""

    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = (
        (STATUS_OPEN, '待处置'),
        (STATUS_RESOLVED, '已处置'),
    )

    target_type = models.CharField('对象类型', max_length=30, choices=TARGET_CHOICES, default=TARGET_TASK)
    target_id = models.BigIntegerField('对象ID')
    level = models.CharField('升级级别', max_length=20, choices=ESCALATION_CHOICES, default=ESCALATION_SUPERVISOR)
    reason = models.CharField('升级原因', max_length=200)
    overdue_at = models.DateTimeField('超期时点', null=True, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    raised_by = models.ForeignKey(
        'users.User', verbose_name='触发人', null=True, blank=True,
        related_name='raised_escalations', on_delete=models.SET_NULL,
    )
    supervisor = models.ForeignKey(
        'users.User', verbose_name='处置主管', null=True, blank=True,
        related_name='handled_escalations', on_delete=models.SET_NULL,
    )
    handle_note = models.CharField('处置说明', max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField('处置时间', null=True, blank=True)

    class Meta:
        db_table = 'escalation_escalation'
        indexes = [
            models.Index(fields=['status', 'target_type', 'target_id']),
        ]
        ordering = ['-id']

    def __str__(self):
        return f'{self.target_type}#{self.target_id} 超期升级'
