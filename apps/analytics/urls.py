from django.urls import path

from .views import (
    AnalyticsOverviewView,
    BookingAnalyticsView,
    ClientAnalyticsView,
    RevenueSnapshotView,
    TrainerBreakdownView,
)

urlpatterns = [
    path("overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("bookings/", BookingAnalyticsView.as_view(), name="analytics-bookings"),
    path("clients/", ClientAnalyticsView.as_view(), name="analytics-clients"),
    path("revenue/", RevenueSnapshotView.as_view(), name="analytics-revenue"),
    path("trainers/", TrainerBreakdownView.as_view(), name="analytics-trainers"),
]
