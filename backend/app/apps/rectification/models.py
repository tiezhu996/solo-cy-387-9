from django.conf import settings
from django.db import models

from app.constants.enums import (
    ORDER_CHOICES,
    ORDER_PENDING,
    SEVERITY_CHOICES,
    SOURCE_CHOICES,
    SOURCE_INSPECTION,
)


class RectificationOrder(models.Model):
    """整改单：由巡检异常项生成，复验通过后随任务关闭。全程保留问题来源。"""

    code = models.CharField('整改单号', max_length=40, unique=True)
    task = models.ForeignKey(
        'inspection.InspectionTask', verbose_name='来源巡检任务',
        related_name='rectification_orders', on_delete=models.PROTECT,
    )
    source = models.CharField('来源类型', max_length=20, choices=SOURCE_CHOICES, default=SOURCE_INSPECTION)
    source_item_name = models.CharField('来源检查项', max_length=120)
    issue_description = models.CharField('问题描述', max_length=500)
    severity = models.CharField('严重程度', max_length=20, choices=SEVERITY_CHOICES, default='medium')
    issue_photos = models.JSONField('问题照片（来源快照）', default=list)

    # 当前待办归属人：为空表示整改单在公共池中待领取
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='当前整改负责人', related_name='rectification_orders',
        null=True, blank=True, on_delete=models.SET_NULL,
    )
    status = models.CharField('整改单状态', max_length=20, choices=ORDER_CHOICES, default=ORDER_PENDING)
    round = models.PositiveIntegerField('整改轮次', default=1)

    due_at = models.DateTimeField('整改期限')
    claimed_at = models.DateTimeField('领取时间', null=True, blank=True)
    submitted_at = models.DateTimeField('最近提交时间', null=True, blank=True)
    verified_at = models.DateTimeField('复验通过时间', null=True, blank=True)
    closed_at = models.DateTimeField('关闭时间', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rectification_order'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['assignee', 'status']),
            models.Index(fields=['due_at']),
        ]
        ordering = ['id']

    def __str__(self):
        return self.code

    @property
    def is_open(self) -> bool:
        return self.status not in ('verified', 'closed')


class RectificationResolution(models.Model):
    """整改处理记录：每一轮整改提交都保留，复验驳回后会产生新一轮。"""

    order = models.ForeignKey(
        RectificationOrder, verbose_name='整改单', related_name='resolutions', on_delete=models.CASCADE
    )
    round = models.PositiveIntegerField('整改轮次')
    rectifier = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='整改人', related_name='rectification_resolutions',
        null=True, on_delete=models.SET_NULL,
    )
    note = models.CharField('处理说明', max_length=500)
    photos = models.JSONField('处理后照片', default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rectification_resolution'
        ordering = ['id']


class RecheckRecord(models.Model):
    """巡检员复验记录：通过或驳回均留痕。"""

    order = models.ForeignKey(
        RectificationOrder, verbose_name='整改单', related_name='rechecks', on_delete=models.CASCADE
    )
    round = models.PositiveIntegerField('复验轮次')
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name='复验巡检员', related_name='rechecks',
        null=True, on_delete=models.SET_NULL,
    )
    passed = models.BooleanField('是否通过')
    note = models.CharField('复验说明', max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'rectification_recheck'
        ordering = ['id']
