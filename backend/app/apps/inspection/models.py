from django.conf import settings
from django.db import models

from app.constants.enums import (
    PERIOD_CHOICES,
    PERIOD_DAILY,
    RESULT_CHOICES,
    TASK_CHOICES,
    TASK_PENDING,
)


class InspectionTask(models.Model):
    """巡检任务：物业按楼栋、区域和周期发布，是整改闭环的根对象。"""

    code = models.CharField('任务编号', max_length=40, unique=True)
    title = models.CharField('任务名称', max_length=120)
    building = models.ForeignKey(
        'organization.Building', verbose_name='楼栋', related_name='inspection_tasks',
        on_delete=models.PROTECT,
    )
    area = models.ForeignKey(
        'organization.Area', verbose_name='巡检区域', related_name='inspection_tasks',
        on_delete=models.PROTECT,
    )
    period = models.CharField('巡检周期', max_length=20, choices=PERIOD_CHOICES, default=PERIOD_DAILY)
    checklist = models.JSONField('检查项清单', default=list)

    publisher = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='发布人', related_name='published_tasks',
        null=True, on_delete=models.SET_NULL,
    )
    # 当前待办归属人：为空表示任务在公共池中待领取
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='当前巡检负责人', related_name='inspection_tasks',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    status = models.CharField('任务状态', max_length=20, choices=TASK_CHOICES, default=TASK_PENDING)

    scheduled_at = models.DateTimeField('计划巡检时间')
    due_at = models.DateTimeField('巡检期限')
    claimed_at = models.DateTimeField('领取时间', null=True, blank=True)
    submitted_at = models.DateTimeField('提交时间', null=True, blank=True)
    closed_at = models.DateTimeField('关闭时间', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inspection_task'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['assignee', 'status']),
            models.Index(fields=['due_at']),
        ]
        ordering = ['-id']

    def __str__(self):
        return f'{self.code} {self.title}'


class InspectionSubmission(models.Model):
    """巡检员对任务的现场提交，一个任务一次提交，可挂多个检查项结果。"""

    task = models.OneToOneField(
        InspectionTask, verbose_name='巡检任务', related_name='submission', on_delete=models.PROTECT
    )
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='巡检员', related_name='inspection_submissions',
        null=True, on_delete=models.SET_NULL,
    )
    summary = models.CharField('总体说明', max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inspection_submission'
        ordering = ['id']


class InspectionItemResult(models.Model):
    """单个检查项的现场结果，异常项会生成对应整改单（来源保留在此）。"""

    submission = models.ForeignKey(
        InspectionSubmission, verbose_name='巡检提交', related_name='items', on_delete=models.CASCADE
    )
    name = models.CharField('检查项', max_length=120)
    result = models.CharField('结果', max_length=20, choices=RESULT_CHOICES)
    description = models.CharField('问题描述', max_length=500, blank=True, default='')
    photos = models.JSONField('现场照片', default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'inspection_item_result'
        ordering = ['id']
