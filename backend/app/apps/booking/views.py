from rest_framework.response import Response
from rest_framework.views import APIView

class BookingCreateView(APIView):
    def post(self, request):
        return Response({'id': 1001, 'status': '待房东确认', 'slot': request.data.get('slot', '周六 10:00')})
