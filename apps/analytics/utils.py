"""Analytics utility helpers."""

from datetime import date, timedelta


def get_date_range(request):
    """
    Return (date_from, date_to, period) from request query params.

    Priority: explicit date_from+date_to > period param > default 'month'.
    """
    date_from_param = request.query_params.get("date_from")
    date_to_param = request.query_params.get("date_to")

    if date_from_param and date_to_param:
        try:
            date_from = date.fromisoformat(date_from_param)
            date_to = date.fromisoformat(date_to_param)
            return date_from, date_to, "custom"
        except ValueError:
            pass

    period = request.query_params.get("period", "month")
    today = date.today()

    if period == "week":
        date_from = today - timedelta(days=7)
    elif period == "month":
        date_from = today.replace(day=1)
    elif period == "3months":
        month = today.month - 3
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        date_from = today.replace(year=year, month=month, day=1)
    elif period == "year":
        date_from = today.replace(month=1, day=1)
    elif period == "all":
        date_from = date(2000, 1, 1)
    else:
        period = "month"
        date_from = today.replace(day=1)

    return date_from, today, period
