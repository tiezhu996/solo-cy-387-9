from rest_framework.response import Response
from rest_framework.views import APIView

class RepairTicketView(APIView):
    def post(self, request):
        return Response({'id': 9001, 'faultType': request.data.get('faultType'), 'description': request.data.get('description'), 'status': '已提交'})
