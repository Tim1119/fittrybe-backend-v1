from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response


class APIResponse:

    @staticmethod
    def success(
        data=None,
        message="Success",
        status_code=status.HTTP_200_OK,
        meta=None,
    ) -> Response:
        payload = {
            "status": "success",
            "message": message,
            "data": data,
            "meta": {
                "timestamp": now().isoformat(),
                "version": "v1",
                **(meta or {}),
            },
        }
        return Response(payload, status=status_code)

    @staticmethod
    def error(
        message="An error occurred",
        errors=None,
        code="ERROR",
        status_code=status.HTTP_400_BAD_REQUEST,
    ) -> Response:
        payload = {
            "status": "error",
            "message": message,
            "errors": errors or {},
            "code": code,
            "meta": {
                "timestamp": now().isoformat(),
                "version": "v1",
            },
        }
        return Response(payload, status=status_code)

    @staticmethod
    def created(data=None, message="Created successfully") -> Response:
        return APIResponse.success(
            data=data,
            message=message,
            status_code=status.HTTP_201_CREATED,
        )

    @staticmethod
    def no_content(message="Deleted successfully") -> Response:
        return Response(
            {"status": "success", "message": message},
            status=status.HTTP_204_NO_CONTENT,
        )
