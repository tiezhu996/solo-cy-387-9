from rest_framework.response import Response
from rest_framework.views import APIView

SAMPLE_PROPERTIES = [
    {'id': 1, 'community': '海棠公寓', 'region': '滨江区', 'layout': '两室一厅', 'area': 76, 'rent': 5200, 'deposit': 5200, 'payment': '月付', 'facilities': ['空调', '洗衣机', '宽带'], 'status': '待出租', 'landlordPhone': '13800000001'},
    {'id': 2, 'community': '梧桐里', 'region': '西湖区', 'layout': '一室一厅', 'area': 48, 'rent': 3900, 'deposit': 3900, 'payment': '季付', 'facilities': ['冰箱', '宽带'], 'status': '已预约', 'landlordPhone': '13800000002'},
]

class PropertyListView(APIView):
    def get(self, request):
        return Response(SAMPLE_PROPERTIES)
