import hashlib
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from api.models import Authentification, Emplacement, JournalSecurite, Reservation, Session, Station, TypeAuth


def hash_secret(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.mark.django_db
def test_create_auth_method_accepts_rfid(authenticated_client, user):
    response = authenticated_client.post(
        reverse("api-auth-method-create"),
        {"auth_mode": "rfid", "auth_value": "RFID-1234"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["auth_method"]["type_label"] == "RFID"
    assert Authentification.objects.filter(utilisateur=user, type_auth__libelle="RFID").exists()


@pytest.mark.django_db
def test_create_auth_method_rejects_non_rfid(authenticated_client):
    response = authenticated_client.post(
        reverse("api-auth-method-create"),
        {"auth_mode": "qr", "auth_value": "QR-1234"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_delete_auth_method_only_deletes_owned_badge(api_client, user):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    badge = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-1234"),
        display_value="RFID-1234",
        expiration=timezone.now() + timedelta(days=365),
    )
    other_user = type(user).objects.create_user(
        pseudo="other-badge",
        email="other-badge@example.com",
        password="OtherPass123!",
    )
    api_client.force_authenticate(user=other_user)

    forbidden_response = api_client.delete(reverse("api-auth-method-delete", kwargs={"auth_id": badge.id_auth}))

    assert forbidden_response.status_code == status.HTTP_404_NOT_FOUND
    assert Authentification.objects.filter(id_auth=badge.id_auth).exists()

    api_client.force_authenticate(user=user)
    delete_response = api_client.delete(reverse("api-auth-method-delete", kwargs={"auth_id": badge.id_auth}))

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    badge.refresh_from_db()
    assert badge.is_active is False
    assert badge.expiration <= timezone.now()


@pytest.mark.django_db
def test_user_can_create_rfid_link_code(authenticated_client):
    response = authenticated_client.post(reverse("api-auth-method-link-code"), {}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert len(response.data["code"]) == 4
    assert response.data["expires_in"] == 600


@pytest.mark.django_db
def test_terminal_link_rfid_consumes_code_and_registers_badge(authenticated_client, api_client, user):
    code_response = authenticated_client.post(reverse("api-auth-method-link-code"), {}, format="json")
    link_code = code_response.data["code"]

    response = api_client.post(
        reverse("api-terminal-link-rfid"),
        {
            "link_code": link_code,
            "uid": "RFID-LINK-1234",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["user"]["pseudo"] == user.pseudo
    assert Authentification.objects.filter(
        utilisateur=user,
        type_auth__libelle="RFID",
        hash_valeur=hash_secret("RFID-LINK-1234"),
        is_active=True,
    ).exists()

    replay_response = api_client.post(
        reverse("api-terminal-link-rfid"),
        {
            "link_code": link_code,
            "uid": "RFID-LINK-1234",
        },
        format="json",
    )

    assert replay_response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_terminal_link_rfid_rejects_badge_already_linked_to_other_user(authenticated_client, api_client, user):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    other_user = type(user).objects.create_user(
        pseudo="linked-other",
        email="linked-other@example.com",
        password="OtherPass123!",
    )
    Authentification.objects.create(
        utilisateur=other_user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-TAKEN"),
        display_value="RFID-TAKEN",
        expiration=timezone.now() + timedelta(days=365),
    )
    code_response = authenticated_client.post(reverse("api-auth-method-link-code"), {}, format="json")

    response = api_client.post(
        reverse("api-terminal-link-rfid"),
        {
            "link_code": code_response.data["code"],
            "uid": "RFID-TAKEN",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert not Authentification.objects.filter(utilisateur=user, hash_valeur=hash_secret("RFID-TAKEN")).exists()


@pytest.mark.django_db
def test_mobile_session_authorizes_and_consumes_reservation(authenticated_client, api_client, user, station, emplacements):
    create_response = api_client.post(
        reverse("api-terminal-mobile-session-create"),
        {"station_id": str(station.id_station)},
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    token = create_response.data["mobile_session"]["token"]
    assert token in create_response.data["url"]

    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="MOBOK1",
        auth_choice="qr",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    detail_response = authenticated_client.get(reverse("api-mobile-session-detail", kwargs={"token": token}))

    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["mobile_session"]["status"] == "pending"
    assert detail_response.data["reservations"][0]["id_reservation"] == str(reservation.id_reservation)
    assert detail_response.data["reservations"][0]["compatible_station"] is True

    authorize_response = authenticated_client.post(
        reverse("api-mobile-session-authorize", kwargs={"token": token}),
        {"reservation_id": str(reservation.id_reservation)},
        format="json",
    )

    assert authorize_response.status_code == status.HTTP_200_OK
    assert authorize_response.data["mobile_session"]["status"] == "authorized"

    status_response = api_client.get(reverse("api-terminal-mobile-session-status", kwargs={"token": token}))

    assert status_response.status_code == status.HTTP_200_OK
    assert status_response.data["reservation"]["reference_code"] == "MOBOK1"

    consume_response = api_client.post(
        reverse("api-terminal-mobile-session-consume", kwargs={"token": token}),
        {"station_id": str(station.id_station)},
        format="json",
    )

    assert consume_response.status_code == status.HTTP_200_OK
    assert consume_response.data["session_created"] is True
    assert consume_response.data["mobile_session"]["status"] == "consumed"
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_mobile_session_authorize_rejects_wrong_station(authenticated_client, api_client, user, station, emplacements):
    other_station = Station.objects.create(
        nom="Station Gare",
        localisation_text="Gare",
        latitude=48.85,
        longitude=2.35,
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    create_response = api_client.post(
        reverse("api-terminal-mobile-session-create"),
        {"station_id": str(station.id_station)},
        format="json",
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=other_emplacement,
        reference_code="MOBBAD1",
        auth_choice="qr",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = authenticated_client.post(
        reverse("api-mobile-session-authorize", kwargs={"token": create_response.data["mobile_session"]["token"]}),
        {"reservation_id": str(reservation.id_reservation)},
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["station"] == other_station.nom
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_terminal_offline_cache_exports_hashes_without_clear_secret(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("OFFLINE-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="OFFLINE1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.get(
        reverse("api-terminal-offline-cache"),
        {"station_id": str(station.id_station)},
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1
    cached = response.data["results"][0]
    assert cached["id_reservation"] == str(reservation.id_reservation)
    assert cached["reference_code"] == "OFFLINE1"
    assert cached["auth_hash"] == hash_secret("OFFLINE-CODE")
    assert "OFFLINE-CODE" not in str(cached)


@pytest.mark.django_db
@override_settings(TERMINAL_API_SECRET="test-terminal-secret")
def test_terminal_offline_cache_requires_terminal_secret(api_client):
    response = api_client.get(reverse("api-terminal-offline-cache"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    authorized_response = api_client.get(
        reverse("api-terminal-offline-cache"),
        HTTP_X_TERMINAL_SECRET="test-terminal-secret",
    )

    assert authorized_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_terminal_offline_events_reconciles_session_started(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-OFFLINE"),
        display_value="RFID-OFFLINE",
        expiration=timezone.now() + timedelta(days=365),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="OFFEVT1",
        authentification=auth_method,
        auth_choice="rfid",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )
    event_payload = {
        "id": "event-start-1",
        "event_type": "offline_session_started",
        "reservation_id": str(reservation.id_reservation),
        "session_id": "offline-local-1",
        "created_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
        "payload": {"auth_mode": "rfid", "reservation": {"id_reservation": str(reservation.id_reservation)}},
    }

    response = api_client.post(
        reverse("api-terminal-offline-events"),
        {"station_id": str(station.id_station), "events": [event_payload]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["synced_event_ids"] == ["event-start-1"]
    assert response.data["accepted"][0]["session_created"] is True
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert Session.objects.filter(reservation=reservation, emplacement=emplacements[0]).exists()
    assert JournalSecurite.objects.filter(action__contains="terminal:offline_session_synced:OFFEVT1").exists()

    replay_response = api_client.post(
        reverse("api-terminal-offline-events"),
        {"station_id": str(station.id_station), "events": [event_payload]},
        format="json",
    )

    assert replay_response.status_code == status.HTTP_200_OK
    assert replay_response.data["accepted"][0]["session_created"] is False
    assert Session.objects.filter(reservation=reservation).count() == 1


@pytest.mark.django_db
def test_terminal_offline_events_rejects_wrong_station(api_client, user, station, emplacements):
    other_station = Station.objects.create(
        nom="Station Gare",
        localisation_text="Gare",
        latitude=48.85,
        longitude=2.35,
        statut="active",
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="OFFBAD1",
        auth_choice="rfid",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-offline-events"),
        {
            "station_id": str(other_station.id_station),
            "events": [
                {
                    "id": "event-wrong-station",
                    "event_type": "offline_session_started",
                    "reservation_id": str(reservation.id_reservation),
                    "session_id": "offline-local-2",
                    "created_at": timezone.now().isoformat(),
                    "payload": {},
                }
            ],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_207_MULTI_STATUS
    assert response.data["accepted"] == []
    assert response.data["rejected"][0]["event_id"] == "event-wrong-station"
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
@override_settings(TERMINAL_API_SECRET="test-terminal-secret")
def test_terminal_offline_events_requires_terminal_secret(api_client):
    response = api_client.post(
        reverse("api-terminal-offline-events"),
        {"events": []},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

    authorized_response = api_client.post(
        reverse("api-terminal-offline-events"),
        {"events": []},
        format="json",
        HTTP_X_TERMINAL_SECRET="test-terminal-secret",
    )

    assert authorized_response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
@override_settings(TERMINAL_API_SECRET="test-terminal-secret")
def test_terminal_browser_flows_require_terminal_secret(api_client):
    authenticate_response = api_client.post(
        reverse("api-terminal-authenticate"),
        {"auth_mode": "rfid", "auth_value": "RFID-1234"},
        format="json",
    )
    mobile_response = api_client.post(reverse("api-terminal-mobile-session-create"), {}, format="json")

    assert authenticate_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert mobile_response.status_code == status.HTTP_401_UNAUTHORIZED

    authorized_response = api_client.post(
        reverse("api-terminal-mobile-session-create"),
        {},
        format="json",
        HTTP_X_TERMINAL_SECRET="test-terminal-secret",
    )

    assert authorized_response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_terminal_authenticate_requires_payload(api_client):
    response = api_client.post(reverse("api-terminal-authenticate"), {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_terminal_authenticate_rejects_wrong_secret(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="BADCODE1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "WRONG-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_terminal_authenticate_rejects_revoked_secret(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
        is_active=False,
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="REVOKED1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "GOOD-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_terminal_authenticate_rejects_wrong_auth_mode(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="MODEBAD1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "qr",
            "auth_value": "GOOD-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "Mauvais moyen d'authentification."
    assert not Session.objects.filter(reservation=reservation).exists()


@pytest.mark.django_db
def test_terminal_authenticate_opens_session_with_valid_code(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="GOODCODE",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "GOOD-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["session_created"] is True
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert Session.objects.filter(reservation=reservation, emplacement=emplacements[0]).exists()


@pytest.mark.django_db
def test_terminal_authenticate_is_idempotent_for_existing_active_session(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="CODE", factor_level=2)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("GOOD-CODE"),
        display_value="****CODE",
        expiration=timezone.now() + timedelta(hours=1),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="IDEMPOT1",
        authentification=auth_method,
        auth_choice="code",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )
    session = Session.objects.create(
        reservation=reservation,
        emplacement=emplacements[0],
        start_time=timezone.now() - timedelta(minutes=2),
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "reservation_code": reservation.reference_code,
            "auth_mode": "code",
            "auth_value": "GOOD-CODE",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["session_created"] is False
    assert response.data["session"]["id"] == str(session.id_session)
    assert Session.objects.filter(reservation=reservation).count() == 1


@pytest.mark.django_db
def test_terminal_authenticate_opens_session_with_direct_rfid(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-1234"),
        display_value="RFID-1234",
        expiration=timezone.now() + timedelta(days=365),
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=emplacements[0],
        reference_code="RFIDOK1",
        authentification=auth_method,
        auth_choice="rfid",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "auth_mode": "rfid",
            "auth_value": "RFID-1234",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["session_created"] is True
    reservation.refresh_from_db()
    assert reservation.statut == "active"
    assert Session.objects.filter(reservation=reservation, emplacement=emplacements[0]).exists()


@pytest.mark.django_db
def test_terminal_authenticate_rejects_direct_rfid_with_multiple_active_reservations(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-MULTI"),
        display_value="RFID-MULTI",
        expiration=timezone.now() + timedelta(days=365),
    )
    for index, emplacement in enumerate(emplacements[:2], start=1):
        Reservation.objects.create(
            utilisateur=user,
            emplacement=emplacement,
            reference_code=f"RFMULT{index}",
            authentification=auth_method,
            auth_choice="rfid",
            date_debut=timezone.now() - timedelta(minutes=5),
            date_fin=timezone.now() + timedelta(minutes=25),
            statut="confirmee",
        )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "auth_mode": "rfid",
            "auth_value": "RFID-MULTI",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "reservations" in response.data
    assert not Session.objects.exists()


@pytest.mark.django_db
def test_terminal_authenticate_rejects_wrong_station(api_client, user, station, emplacements):
    type_auth = TypeAuth.objects.create(libelle="RFID", factor_level=1)
    auth_method = Authentification.objects.create(
        utilisateur=user,
        type_auth=type_auth,
        hash_valeur=hash_secret("RFID-STATION"),
        display_value="RFID-STATION",
        expiration=timezone.now() + timedelta(days=365),
    )
    other_station = Station.objects.create(
        nom="Station Gare",
        localisation_text="Gare",
        latitude=48.85,
        longitude=2.35,
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    reservation = Reservation.objects.create(
        utilisateur=user,
        emplacement=other_emplacement,
        reference_code="WRONGST",
        authentification=auth_method,
        auth_choice="rfid",
        date_debut=timezone.now() - timedelta(minutes=5),
        date_fin=timezone.now() + timedelta(minutes=25),
        statut="confirmee",
    )

    response = api_client.post(
        reverse("api-terminal-authenticate"),
        {
            "auth_mode": "rfid",
            "auth_value": "RFID-STATION",
            "station_id": str(station.id_station),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.data["station"] == other_station.nom
    assert not Session.objects.filter(reservation=reservation).exists()
