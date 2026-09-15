from rest_framework import serializers

from .models import RecheckRecord, RectificationOrder, RectificationResolution


class ResolutionOutSerializer(serializers.ModelSerializer):
    rectifier_name = serializers.CharField(source='rectifier.name', read_only=True, default='')

    class Meta:
        model = RectificationResolution
        fields = ['id', 'round', 'rectifier_name', 'note', 'photos', 'created_at']


class RecheckOutSerializer(serializers.ModelSerializer):
    inspector_name = serializers.CharField(source='inspector.name', read_only=True, default='')

    class Meta:
        model = RecheckRecord
        fields = ['id', 'round', 'inspector_name', 'passed', 'note', 'created_at']


class OrderListSerializer(serializers.ModelSerializer):
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    severity_label = serializers.CharField(source='get_severity_display', read_only=True)
    source_label = serializers.CharField(source='get_source_display', read_only=True)
    assignee_name = serializers.CharField(source='assignee.name', read_only=True, default=None)
    task_code = serializers.CharField(source='task.code', read_only=True)
    task_title = serializers.CharField(source='task.title', read_only=True)
    overdue = serializers.SerializerMethodField()

    class Meta:
        model = RectificationOrder
        fields = [
            'id', 'code', 'task', 'task_code', 'task_title', 'source', 'source_label',
            'source_item_name', 'issue_description', 'severity', 'severity_label',
            'issue_photos', 'assignee', 'assignee_name', 'status', 'status_label', 'round',
            'due_at', 'claimed_at', 'submitted_at', 'verified_at', 'closed_at',
            'created_at', 'overdue',
        ]

    def get_overdue(self, obj):
        from django.utils import timezone
        return obj.is_open and obj.due_at < timezone.now()


class OrderDetailSerializer(OrderListSerializer):
    resolutions = ResolutionOutSerializer(many=True, read_only=True)
    rechecks = RecheckOutSerializer(many=True, read_only=True)

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + ['resolutions', 'rechecks']


class SubmitResolutionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=500)
    photos = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class RecheckSerializer(serializers.Serializer):
    passed = serializers.BooleanField()
    note = serializers.CharField(required=False, allow_blank=True, default='')


class ReassignOrderSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
