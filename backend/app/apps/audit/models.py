from django.db import models

from app.constants.enums import TARGET_CHOICES, TARGET_TASK


class StatusHistory(models.Model):
    """巡检任务 / 整改单的完整状态流转历史，只增不改，闭环全程可追溯。"""

    TARGET_TASK = 'task'
    TARGET_ORDER = 'rectification_order'

    target_type = models.CharField('对象类型', max_length=30, choices=TARGET_CHOICES, default=TARGET_TASK)
    target_id = models.BigIntegerField('对象ID')
    action = models.CharField('动作', max_length=40)
    from_status = models.CharField('变更前状态', max_length=30, blank=True, default='')
    to_status = models.CharField('变更后状态', max_length=30, blank=True, default='')
    actor = models.ForeignKey(
        'users.User', verbose_name='操作人', null=True, blank=True,
        related_name='status_histories', on_delete=models.SET_NULL,
    )
    actor_name = models.CharField('操作人姓名快照', max_length=40, blank=True, default='')
    detail = models.CharField('说明', max_length=500, blank=True, default='')
    created_at = models.DateTimeField('发生时间', auto_now_add=True)

    class Meta:
        db_table = 'audit_status_history'
        indexes = [models.Index(fields=['target_type', 'target_id', 'created_at'])]
        ordering = ['id']

    def __str__(self):
        return f'{self.target_type}#{self.target_id} {self.action}'
