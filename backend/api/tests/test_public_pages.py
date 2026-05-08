from django.test import Client
from django.urls import reverse


def test_cgu_page_is_public():
    response = Client().get(reverse("cgu"))

    assert response.status_code == 200
    assert "Conditions g&eacute;n&eacute;rales d'utilisation" in response.content.decode()


def test_privacy_page_is_public_and_mentions_session_cookie():
    response = Client().get(reverse("privacy"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Politique de confidentialit&eacute;" in content
    assert "HttpOnly" in content
