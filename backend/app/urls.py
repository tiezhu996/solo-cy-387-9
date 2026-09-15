from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from app.api_media import PhotoUploadView
from app.apps.users.views import LoginView, LogoutView, MeView, demo_accounts
from app.apps.users.admin_views import UserActiveView, UserListView
from app.apps.organization.views import AreaListCreateView, BuildingListCreateView
from app.apps.inspection.views import (
    TaskClaimView,
    TaskCloseView,
    TaskDetailView,
    TaskListCreateView,
    TaskReassignView,
    TaskRescheduleView,
    TaskSubmitView,
    TaskTimelineView,
)
from app.apps.rectification.views import (
    OrderClaimView,
    OrderCloseView,
    OrderDetailView,
    OrderListView,
    OrderReassignView,
    OrderRecheckView,
    OrderSubmitView,
)
from app.apps.escalation.views import EscalationListView, EscalationResolveView

api = [
    # 认证 / 用户
    path('api/auth/login/', LoginView.as_view()),
    path('api/auth/logout/', LogoutView.as_view()),
    path('api/auth/me/', MeView.as_view()),
    path('api/auth/demo-accounts/', demo_accounts),
    path('api/users/', UserListView.as_view()),
    path('api/users/<int:user_id>/active/', UserActiveView.as_view()),

    # 组织
    path('api/buildings/', BuildingListCreateView.as_view()),
    path('api/areas/', AreaListCreateView.as_view()),

    # 巡检任务
    path('api/tasks/', TaskListCreateView.as_view()),
    path('api/tasks/<int:task_id>/', TaskDetailView.as_view()),
    path('api/tasks/<int:task_id>/claim/', TaskClaimView.as_view()),
    path('api/tasks/<int:task_id>/submit/', TaskSubmitView.as_view()),
    path('api/tasks/<int:task_id>/close/', TaskCloseView.as_view()),
    path('api/tasks/<int:task_id>/reschedule/', TaskRescheduleView.as_view()),
    path('api/tasks/<int:task_id>/reassign/', TaskReassignView.as_view()),
    path('api/tasks/<int:task_id>/timeline/', TaskTimelineView.as_view()),

    # 整改单
    path('api/orders/', OrderListView.as_view()),
    path('api/orders/<int:order_id>/', OrderDetailView.as_view()),
    path('api/orders/<int:order_id>/claim/', OrderClaimView.as_view()),
    path('api/orders/<int:order_id>/submit/', OrderSubmitView.as_view()),
    path('api/orders/<int:order_id>/recheck/', OrderRecheckView.as_view()),
    path('api/orders/<int:order_id>/close/', OrderCloseView.as_view()),
    path('api/orders/<int:order_id>/reassign/', OrderReassignView.as_view()),

    # 超期升级
    path('api/escalations/', EscalationListView.as_view()),
    path('api/escalations/<int:escalation_id>/resolve/', EscalationResolveView.as_view()),

    # 照片
    path('api/photos/', PhotoUploadView.as_view()),
]

urlpatterns = api + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
