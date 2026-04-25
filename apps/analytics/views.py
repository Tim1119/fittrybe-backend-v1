"""Analytics views — all data is computed on-the-fly from existing models."""

from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.permissions import IsGym, IsTrainerOrGym
from apps.clients.models import ClientMembership
from apps.core.pagination import StandardPagination
from apps.core.responses import APIResponse
from apps.marketplace.models import Product, ProductEnquiry
from apps.sessions.models import Session
from apps.subscriptions.models import PaymentRecord

from .utils import get_date_range


def _use_weekly_grouping(period, date_from, date_to):
    """Return True when sessions should be bucketed by week rather than month."""
    if period in ("week", "month"):
        return True
    if period == "custom":
        return (date_to - date_from).days <= 31
    return False


class AnalyticsOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Get analytics overview",
        description=(
            "Returns a summary of key metrics for the authenticated trainer or gym. "
            "Accepts optional `period` (week|month|3months|year|all, default month) "
            "or explicit `date_from`/`date_to` (YYYY-MM-DD) query params. "
            "`total_active_clients` is always current (not date-filtered). "
            "Trainer accounts scope data to their own profile; gym accounts scope "
            "to all trainers and memberships under their gym."
        ),
        responses={
            200: OpenApiResponse(description="Analytics overview data"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(
                description="Permission denied — clients cannot access this endpoint"
            ),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        date_from, date_to, period = get_date_range(request)

        if request.user.role == "trainer":
            trainer_profile = request.user.trainer_profile
            sessions_qs = Session.objects.filter(trainer=trainer_profile)
            memberships_qs = ClientMembership.objects.filter(trainer=trainer_profile)
            products_qs = Product.objects.filter(trainer=trainer_profile)
        else:
            gym_profile = request.user.gym_profile
            sessions_qs = Session.objects.filter(trainer__gym=gym_profile)
            memberships_qs = ClientMembership.objects.filter(gym=gym_profile)
            products_qs = Product.objects.filter(gym=gym_profile)

        period_sessions = sessions_qs.filter(
            session_date__gte=date_from,
            session_date__lte=date_to,
        )

        enquiries_count = ProductEnquiry.objects.filter(
            product__in=products_qs,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).count()

        data = {
            "total_active_clients": memberships_qs.filter(
                status=ClientMembership.Status.ACTIVE
            ).count(),
            "total_sessions": period_sessions.count(),
            "total_completed_sessions": period_sessions.filter(
                status=Session.Status.COMPLETED
            ).count(),
            "total_cancelled_sessions": period_sessions.filter(
                status=Session.Status.CANCELLED
            ).count(),
            "total_no_show_sessions": period_sessions.filter(
                status=Session.Status.NO_SHOW
            ).count(),
            "new_clients_this_period": memberships_qs.filter(
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            ).count(),
            "marketplace_enquiries": enquiries_count,
            "physical_sessions": period_sessions.filter(
                session_type=Session.SessionType.PHYSICAL
            ).count(),
            "virtual_sessions": period_sessions.filter(
                session_type=Session.SessionType.VIRTUAL
            ).count(),
            "period": period,
            "date_from": str(date_from),
            "date_to": str(date_to),
        }

        return APIResponse.success(data=data, message="Analytics overview retrieved")


class BookingAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Get booking analytics",
        description=(
            "Returns session booking breakdown including totals by status and type, "
            "completion rate (completed / total * 100), and a time-series `by_period` "
            "list. `by_period` groups by week for period <= month, by month for longer "
            "periods. Accepts `period` or `date_from`/`date_to` query params."
        ),
        responses={
            200: OpenApiResponse(description="Booking analytics data"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        date_from, date_to, period = get_date_range(request)

        if request.user.role == "trainer":
            sessions_qs = Session.objects.filter(trainer=request.user.trainer_profile)
        else:
            sessions_qs = Session.objects.filter(trainer__gym=request.user.gym_profile)

        period_sessions = sessions_qs.filter(
            session_date__gte=date_from,
            session_date__lte=date_to,
        )

        total = period_sessions.count()
        completed = period_sessions.filter(status=Session.Status.COMPLETED).count()
        cancelled = period_sessions.filter(status=Session.Status.CANCELLED).count()
        no_show = period_sessions.filter(status=Session.Status.NO_SHOW).count()
        completion_rate = round(completed / total * 100, 1) if total > 0 else 0.0

        trunc_fn = (
            TruncWeek
            if _use_weekly_grouping(period, date_from, date_to)
            else TruncMonth
        )
        raw_periods = (
            period_sessions.annotate(label=trunc_fn("session_date"))
            .values("label")
            .annotate(count=Count("id"))
            .order_by("label")
        )
        by_period = [
            {"label": str(item["label"]), "count": item["count"]}
            for item in raw_periods
        ]

        data = {
            "total": total,
            "completed": completed,
            "cancelled": cancelled,
            "no_show": no_show,
            "physical": period_sessions.filter(
                session_type=Session.SessionType.PHYSICAL
            ).count(),
            "virtual": period_sessions.filter(
                session_type=Session.SessionType.VIRTUAL
            ).count(),
            "completion_rate": completion_rate,
            "by_period": by_period,
            "period": period,
        }

        return APIResponse.success(data=data, message="Booking analytics retrieved")


class ClientAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Get client analytics",
        description=(
            "Returns client membership breakdown by status, new clients joined in the "
            "period, and retention rate (active / (active + lapsed) * 100, 0.0 when "
            "no clients). Accepts `period` or `date_from`/`date_to` query params."
        ),
        responses={
            200: OpenApiResponse(description="Client analytics data"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        date_from, date_to, period = get_date_range(request)

        if request.user.role == "trainer":
            memberships_qs = ClientMembership.objects.filter(
                trainer=request.user.trainer_profile
            )
        else:
            memberships_qs = ClientMembership.objects.filter(
                gym=request.user.gym_profile
            )

        total_active = memberships_qs.filter(
            status=ClientMembership.Status.ACTIVE
        ).count()
        total_lapsed = memberships_qs.filter(
            status=ClientMembership.Status.LAPSED
        ).count()
        total_pending = memberships_qs.filter(
            status=ClientMembership.Status.PENDING
        ).count()

        base = total_active + total_lapsed
        retention_rate = round(total_active / base * 100, 1) if base > 0 else 0.0

        new_this_period = memberships_qs.filter(
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).count()

        data = {
            "total_active": total_active,
            "total_lapsed": total_lapsed,
            "total_pending": total_pending,
            "new_this_period": new_this_period,
            "retention_rate": retention_rate,
            "period": period,
        }

        return APIResponse.success(data=data, message="Client analytics retrieved")


class RevenueSnapshotView(APIView):
    permission_classes = [IsAuthenticated, IsTrainerOrGym]

    @extend_schema(
        summary="Get revenue snapshot",
        description=(
            "Returns platform subscription revenue paid by the current user (NGN and "
            "USD). Only successful payments with a paid_at date in the selected range "
            "are counted. Trainer-to-client payments are handled manually in V1 and "
            "are not tracked here. `marketplace_enquiry_count` is a proxy for product "
            "sales interest. Accepts `period` or `date_from`/`date_to` query params."
        ),
        responses={
            200: OpenApiResponse(description="Revenue snapshot data"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied"),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        date_from, date_to, period = get_date_range(request)

        if request.user.role == "trainer":
            products_qs = Product.objects.filter(trainer=request.user.trainer_profile)
        else:
            products_qs = Product.objects.filter(gym=request.user.gym_profile)

        base_payments = PaymentRecord.objects.filter(
            subscription__user=request.user,
            status=PaymentRecord.Status.SUCCESS,
            paid_at__date__gte=date_from,
            paid_at__date__lte=date_to,
        )

        ngn_total = base_payments.filter(currency="NGN").aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")
        usd_total = base_payments.filter(currency="USD").aggregate(total=Sum("amount"))[
            "total"
        ] or Decimal("0.00")

        enquiry_count = ProductEnquiry.objects.filter(
            product__in=products_qs,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        ).count()

        data = {
            "platform_revenue_ngn": f"{ngn_total:.2f}",
            "platform_revenue_usd": f"{usd_total:.2f}",
            "marketplace_enquiry_count": enquiry_count,
            "note": (
                "Trainer-to-client payments are manual in V1. "
                "Revenue shown is your platform subscription payments only."
            ),
            "period": period,
        }

        return APIResponse.success(data=data, message="Revenue snapshot retrieved")


class TrainerBreakdownView(APIView):
    permission_classes = [IsAuthenticated, IsGym]

    @extend_schema(
        summary="Get per-trainer analytics breakdown (gym only)",
        description=(
            "Returns a paginated list of all trainers under this gym, each with "
            "individual stats: sessions, active clients, and marketplace data for the "
            "selected period. This is a Pro plan (gym) feature — trainer accounts will "
            "receive 403. Accepts `period` or `date_from`/`date_to` query params."
        ),
        responses={
            200: OpenApiResponse(description="Paginated per-trainer breakdown"),
            401: OpenApiResponse(description="Authentication required"),
            403: OpenApiResponse(description="Permission denied — gym accounts only"),
        },
        tags=["Analytics"],
    )
    def get(self, request):
        date_from, date_to, period = get_date_range(request)
        gym_profile = request.user.gym_profile
        trainers = gym_profile.gym_trainers.all()

        trainer_data = []
        for trainer in trainers:
            sessions_qs = Session.objects.filter(
                trainer=trainer,
                session_date__gte=date_from,
                session_date__lte=date_to,
            )
            products_qs = Product.objects.filter(trainer=trainer)
            trainer_data.append(
                {
                    "trainer_id": trainer.id,
                    "trainer_name": trainer.full_name,
                    "active_clients": ClientMembership.objects.filter(
                        trainer=trainer,
                        status=ClientMembership.Status.ACTIVE,
                    ).count(),
                    "total_sessions": sessions_qs.count(),
                    "completed_sessions": sessions_qs.filter(
                        status=Session.Status.COMPLETED
                    ).count(),
                    "cancelled_sessions": sessions_qs.filter(
                        status=Session.Status.CANCELLED
                    ).count(),
                    "marketplace_products": products_qs.count(),
                    "marketplace_enquiries": ProductEnquiry.objects.filter(
                        product__in=products_qs,
                        created_at__date__gte=date_from,
                        created_at__date__lte=date_to,
                    ).count(),
                }
            )

        paginator = StandardPagination()
        page = paginator.paginate_queryset(trainer_data, request)
        return paginator.get_paginated_response(page)
