from rest_framework import serializers
from .models import Property

class PropertySerializer(serializers.ModelSerializer):
    landlordPhone = serializers.CharField(source='landlord_phone')

    class Meta:
        model = Property
        fields = ['id', 'community', 'region', 'layout', 'area', 'rent', 'deposit', 'payment', 'facilities', 'status', 'landlordPhone']
