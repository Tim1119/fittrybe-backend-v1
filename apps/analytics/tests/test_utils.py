"""Tests for analytics utility functions."""

from datetime import date, timedelta
from unittest.mock import MagicMock


def make_request(**params):
    req = MagicMock()
    req.query_params = params
    return req


class TestGetDateRange:
    def test_default_period_is_month(self):
        from apps.analytics.utils import get_date_range

        req = make_request()
        date_from, date_to, period = get_date_range(req)
        today = date.today()
        assert period == "month"
        assert date_from == today.replace(day=1)
        assert date_to == today

    def test_period_week(self):
        from apps.analytics.utils import get_date_range

        req = make_request(period="week")
        date_from, date_to, period = get_date_range(req)
        today = date.today()
        assert period == "week"
        assert date_from == today - timedelta(days=7)
        assert date_to == today

    def test_period_3months(self):
        from apps.analytics.utils import get_date_range

        req = make_request(period="3months")
        date_from, date_to, period = get_date_range(req)
        today = date.today()
        assert period == "3months"
        assert date_to == today
        # date_from should be roughly 3 months ago — just check it's before this month
        assert date_from < today.replace(day=1)

    def test_period_year(self):
        from apps.analytics.utils import get_date_range

        req = make_request(period="year")
        date_from, date_to, period = get_date_range(req)
        today = date.today()
        assert period == "year"
        assert date_from == today.replace(month=1, day=1)
        assert date_to == today

    def test_period_all(self):
        from apps.analytics.utils import get_date_range

        req = make_request(period="all")
        date_from, date_to, period = get_date_range(req)
        assert period == "all"
        assert date_from == date(2000, 1, 1)

    def test_custom_date_range_overrides_period(self):
        from apps.analytics.utils import get_date_range

        req = make_request(date_from="2025-01-01", date_to="2025-01-31", period="week")
        date_from, date_to, period = get_date_range(req)
        assert date_from == date(2025, 1, 1)
        assert date_to == date(2025, 1, 31)
        assert period == "custom"

    def test_partial_custom_range_falls_back_to_period(self):
        from apps.analytics.utils import get_date_range

        req = make_request(date_from="2025-01-01")  # missing date_to
        date_from, date_to, period = get_date_range(req)
        assert period == "month"

    def test_invalid_period_defaults_to_month(self):
        from apps.analytics.utils import get_date_range

        req = make_request(period="quarterly")
        date_from, date_to, period = get_date_range(req)
        assert period == "month"

    def test_invalid_custom_dates_fall_back_to_period(self):
        from apps.analytics.utils import get_date_range

        req = make_request(date_from="not-a-date", date_to="also-not-a-date")
        date_from, date_to, period = get_date_range(req)
        assert period == "month"

    def test_3months_crosses_year_boundary(self):
        from unittest.mock import patch

        from apps.analytics.utils import get_date_range

        # Simulate today = 2025-02-15 → 3 months back = 2024-11-01
        fake_today = date(2025, 2, 15)
        with patch("apps.analytics.utils.date") as mock_date:
            mock_date.today.return_value = fake_today
            mock_date.side_effect = lambda *args, **kw: date(*args, **kw)
            req = make_request(period="3months")
            date_from, date_to, period = get_date_range(req)

        assert date_from == date(2024, 11, 1)
        assert period == "3months"
