"""主管升级台：查看超期升级单、处置。"""

from rest_framework.views import APIView

from app.constants.errors import BusinessError
from app.utils.permissions import IsPropertyOrSupervisor, IsSupervisor
from app.utils.response import ok
from .models import Escalation
from . import services
from .serializers import decorate


class EscalationListView(APIView):
    """主管看全部；物业管理员可只读查看。"""

    permission_classes = [IsPropertyOrSupervisor]

    def get(self, request):
        status = request.query_params.get('status', Escalation.STATUS_OPEN)
        qs = Escalation.objects.all()
        if status in ('open', 'resolved'):
            qs = qs.filter(status=status)
        escalations = list(qs.order_by('-id')[:200])
        return ok(decorate(escalations))


class EscalationResolveView(APIView):
    permission_classes = [IsSupervisor]

    def post(self, request, escalation_id):
        note = (request.data.get('note') or '').strip() or '已处理'
        esc = services.resolve_escalation(escalation_id, request.user, note)
        return ok({'id': esc.id, 'status': esc.status})
