import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_register_endpoint_returns_tokens_and_user_payload():
    response = APIClient().post(
        reverse("api-register"),
        {
            "pseudo": "bob",
            "email": "bob@example.com",
            "telephone": "0600000000",
            "password": "ValidPass123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["user"]["pseudo"] == "bob"
    assert "access" in response.data
    assert "refresh" in response.data
