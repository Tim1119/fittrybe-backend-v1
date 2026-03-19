from django.utils.timezone import now
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100
    page_query_param = "page"

    def get_paginated_response(self, data):
        return Response(
            {
                "status": "success",
                "message": "Data retrieved successfully",
                "data": data,
                "meta": {
                    "timestamp": now().isoformat(),
                    "version": "v1",
                    "pagination": {
                        "total_count": self.page.paginator.count,
                        "total_pages": self.page.paginator.num_pages,
                        "current_page": self.page.number,
                        "page_size": self.get_page_size(self.request),
                        "next": self.get_next_link(),
                        "previous": self.get_previous_link(),
                    },
                },
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "message": {"type": "string"},
                "data": schema,
                "meta": {
                    "type": "object",
                    "properties": {
                        "pagination": {
                            "type": "object",
                            "properties": {
                                "total_count": {"type": "integer"},
                                "total_pages": {"type": "integer"},
                                "current_page": {"type": "integer"},
                                "page_size": {"type": "integer"},
                                "next": {"type": "string", "nullable": True},
                                "previous": {"type": "string", "nullable": True},
                            },
                        }
                    },
                },
            },
        }
