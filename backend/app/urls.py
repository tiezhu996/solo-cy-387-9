from django.urls import path
from app.apps.properties.views import PropertyListView
from app.apps.booking.views import BookingCreateView
from app.apps.contract.views import ContractListView
from app.apps.repair.views import RepairTicketView

urlpatterns = [
    path('api/properties/', PropertyListView.as_view()),
    path('api/bookings/', BookingCreateView.as_view()),
    path('api/contracts/', ContractListView.as_view()),
    path('api/repairs/', RepairTicketView.as_view()),
]
