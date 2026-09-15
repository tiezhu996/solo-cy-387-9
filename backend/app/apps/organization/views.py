"""楼栋与巡检区域：物业维护，其他角色只读。"""

from rest_framework.views import APIView

from app.constants.errors import BusinessError
from app.utils.permissions import ActiveUserPermission, IsProperty
from app.utils.response import ok
from .models import Area, Building
from .serializers import AreaSerializer, BuildingSerializer


class BuildingListCreateView(APIView):
    def get_permissions(self):
        return [IsProperty()] if self.request.method == 'POST' else [ActiveUserPermission()]

    def get(self, request):
        buildings = Building.objects.all()
        return ok(BuildingSerializer(buildings, many=True).data)

    def post(self, request):
        serializer = BuildingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return ok(serializer.data, status_code=201)


class AreaListCreateView(APIView):
    def get_permissions(self):
        return [IsProperty()] if self.request.method == 'POST' else [ActiveUserPermission()]

    def get(self, request):
        areas = Area.objects.select_related('building').all()
        building_id = request.query_params.get('building')
        if building_id:
            areas = areas.filter(building_id=building_id)
        return ok(AreaSerializer(areas, many=True).data)

    def post(self, request):
        serializer = AreaSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not Building.objects.filter(pk=serializer.validated_data['building'].pk).exists():
            raise BusinessError('BUILDING_NOT_FOUND', 404)
        serializer.save()
        return ok(serializer.data, status_code=201)
