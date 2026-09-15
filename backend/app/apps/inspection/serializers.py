from rest_framework import serializers

from .models import InspectionItemResult, InspectionSubmission, InspectionTask


class TaskPublishSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=120)
    building_id = serializers.IntegerField()
    area_id = serializers.IntegerField()
    period = serializers.ChoiceField(choices=['daily', 'weekly', 'monthly'])
    scheduled_at = serializers.DateTimeField()
    due_at = serializers.DateTimeField()
    checklist = serializers.ListField(
        child=serializers.CharField(max_length=120), allow_empty=False
    )
    assignee_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, data):
        if data['due_at'] <= data['scheduled_at']:
            raise serializers.ValidationError('巡检期限必须晚于计划巡检时间')
        return data


class ItemResultSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    result = serializers.ChoiceField(choices=['normal', 'issue'])
    description = serializers.CharField(required=False, allow_blank=True, default='')
    photos = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )


class SubmitInspectionSerializer(serializers.Serializer):
    summary = serializers.CharField(required=False, allow_blank=True, default='')
    items = ItemResultSerializer(many=True)


class RescheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()
    due_at = serializers.DateTimeField()

    def validate(self, data):
        if data['due_at'] <= data['scheduled_at']:
            raise serializers.ValidationError('巡检期限必须晚于计划巡检时间')
        return data


class ReassignSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    to_pool = serializers.BooleanField(required=False, default=False)


class ItemResultOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = InspectionItemResult
        fields = ['id', 'name', 'result', 'description', 'photos']


class SubmissionOutSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(source='inspector.name', read_only=True, default='')
    items = ItemResultOutSerializer(many=True, read_only=True)

    class Meta:
        model = InspectionSubmission
        fields = ['id', 'inspector_name', 'summary', 'created_at', 'items']


class TaskListSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)
    area_name = serializers.CharField(source='area.name', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    period_label = serializers.CharField(source='get_period_display', read_only=True)
    assignee_name = serializers.CharField(source='assignee.name', read_only=True, default=None)
    open_order_count = serializers.IntegerField(read_only=True, default=0)
    overdue = serializers.SerializerMethodField()

    class Meta:
        model = InspectionTask
        fields = [
            'id', 'code', 'title', 'building_name', 'area_name', 'period', 'period_label',
            'status', 'status_label', 'assignee', 'assignee_name',
            'scheduled_at', 'due_at', 'claimed_at', 'submitted_at', 'closed_at',
            'created_at', 'open_order_count', 'overdue',
        ]

    def get_overdue(self, obj):
        from django.utils import timezone
        return obj.status != 'done' and obj.due_at < timezone.now()


class TaskDetailSerializer(TaskListSerializer):
    checklist = serializers.JSONField()
    publisher_name = serializers.CharField(source='publisher.name', read_only=True, default=None)
    submission = SubmissionOutSerializer(read_only=True)

    class Meta(TaskListSerializer.Meta):
        fields = TaskListSerializer.Meta.fields + ['checklist', 'publisher_name', 'submission']
