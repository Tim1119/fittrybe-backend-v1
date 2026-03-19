"""
Tests for apps.core.responses and apps.core.pagination.
"""

from rest_framework import status
from rest_framework.response import Response

from apps.core.responses import APIResponse


class TestAPIResponseSuccess:
    def test_default_success(self):
        response = APIResponse.success(data={"id": 1})
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"
        assert response.data["message"] == "Success"
        assert response.data["data"] == {"id": 1}
        assert "timestamp" in response.data["meta"]
        assert response.data["meta"]["version"] == "v1"

    def test_custom_message_and_status(self):
        response = APIResponse.success(
            data=[1, 2, 3],
            message="All good",
            status_code=status.HTTP_202_ACCEPTED,
        )
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data["message"] == "All good"
        assert response.data["data"] == [1, 2, 3]

    def test_meta_merging(self):
        response = APIResponse.success(data=None, meta={"extra": "value"})
        assert response.data["meta"]["extra"] == "value"
        assert "timestamp" in response.data["meta"]

    def test_none_data(self):
        response = APIResponse.success()
        assert response.data["data"] is None


class TestAPIResponseError:
    def test_default_error(self):
        response = APIResponse.error()
        assert isinstance(response, Response)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["status"] == "error"
        assert response.data["message"] == "An error occurred"
        assert response.data["code"] == "ERROR"
        assert response.data["errors"] == {}

    def test_custom_error(self):
        response = APIResponse.error(
            message="Not found",
            errors={"detail": "Resource missing"},
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["message"] == "Not found"
        assert response.data["code"] == "NOT_FOUND"
        assert response.data["errors"] == {"detail": "Resource missing"}

    def test_errors_defaults_to_empty_dict_when_none(self):
        response = APIResponse.error(errors=None)
        assert response.data["errors"] == {}


class TestAPIResponseCreated:
    def test_created(self):
        response = APIResponse.created(data={"id": 99}, message="User created")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == "success"
        assert response.data["message"] == "User created"
        assert response.data["data"] == {"id": 99}


class TestAPIResponseNoContent:
    def test_no_content(self):
        response = APIResponse.no_content()
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.data["status"] == "success"

    def test_custom_message(self):
        response = APIResponse.no_content(message="Item removed")
        assert response.data["message"] == "Item removed"
