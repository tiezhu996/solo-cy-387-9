from rest_framework import serializers

from .models import Escalation


class EscalationSerializer(serializers.ModelSerializer):
    target_code = serializers.CharField(read_only=True, default='')
    target_title = serializers.CharField(read_only=True, default='')
    status_label = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Escalation
        fields = [
            'id', 'target_type', 'target_id', 'target_code', 'target_title',
            'level', 'reason', 'overdue_at', 'status', 'status_label',
            'handle_note', 'created_at', 'resolved_at',
        ]


def decorate(escalations):
    """为升级单批量补充对象编号与标题，避免逐条查询。"""
    from app.apps.inspection.models import InspectionTask
    from app.apps.rectification.models import RectificationOrder

    task_ids = [e.target_id for e in escalations if e.target_type == 'task']
    order_ids = [e.target_id for e in escalations if e.target_type == 'rectification_order']
    tasks = {t.id: t for t in InspectionTask.objects.filter(id__in=task_ids)}
    orders = {o.id: o for o in RectificationOrder.objects.filter(id__in=order_ids)}
    data = EscalationSerializer(escalations, many=True).data
    for item, esc in zip(data, escalations):
        if esc.target_type == 'task':
            t = tasks.get(esc.target_id)
            item['target_code'] = t.code if t else ''
            item['target_title'] = t.title if t else '（任务不存在）'
        else:
            o = orders.get(esc.target_id)
            item['target_code'] = o.code if o else ''
            item['target_title'] = o.issue_description[:40] if o else '（整改单不存在）'
    return data
