from rest_framework import serializers

from .models import Area, Building


class BuildingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Building
        fields = ['id', 'code', 'name']


class AreaSerializer(serializers.ModelSerializer):
    building_name = serializers.CharField(source='building.name', read_only=True)

    class Meta:
        model = Area
        fields = ['id', 'building', 'building_name', 'code', 'name', 'location']
