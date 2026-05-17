import asyncio

import pytest
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

from api.models import Borne, Device, Emplacement, Station, Technicien, TechnicienStation
from config.asgi import application


@pytest.mark.django_db(transaction=True)
def test_admin_supervision_websocket_accepts_staff_user(admin_user):
    token = str(RefreshToken.for_user(admin_user).access_token)

    async def scenario():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/admin/supervision/?token={token}",
            headers=[(b"host", b"localhost"), (b"origin", b"http://localhost")],
        )
        connected, close_code = await communicator.connect()
        assert connected is True, close_code

        message = await communicator.receive_json_from(timeout=3)
        assert message["type"] == "supervision.snapshot"
        assert "stats" in message["payload"]

        await communicator.disconnect()

    asyncio.run(scenario())


@pytest.mark.django_db(transaction=True)
def test_admin_supervision_websocket_rejects_regular_user(user):
    token = str(RefreshToken.for_user(user).access_token)

    async def scenario():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/admin/supervision/?token={token}",
            headers=[(b"host", b"localhost"), (b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        assert connected is False

    asyncio.run(scenario())


@pytest.mark.django_db(transaction=True)
def test_technician_supervision_websocket_returns_assigned_station_scope(user, station, emplacements):
    technicien = Technicien.objects.create(
        utilisateur=user,
        nom="Tech Temps Reel",
        email="tech-realtime@example.com",
    )
    TechnicienStation.objects.create(technicien=technicien, station=station)
    Device.objects.create(
        emplacement=emplacements[0],
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-assigned",
        status="charging",
    )
    other_station = Station.objects.create(
        nom="Station Nord",
        localisation_text="Quartier Nord",
        statut="active",
    )
    other_borne = Borne.objects.create(
        station=other_station,
        numero=1,
        nom="Borne Nord",
        statut="active",
    )
    other_emplacement = Emplacement.objects.create(
        station=other_station,
        borne=other_borne,
        numero=1,
        statut="disponible",
        lock_state="verrouille",
    )
    Device.objects.create(
        emplacement=other_emplacement,
        type_device="ESP32",
        firmware_version="1.0.0",
        mac_address="slot-other",
        status="charging",
    )
    token = str(RefreshToken.for_user(user).access_token)

    async def scenario():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/technician/supervision/?token={token}",
            headers=[(b"host", b"localhost"), (b"origin", b"http://localhost")],
        )
        connected, close_code = await communicator.connect()
        assert connected is True, close_code

        message = await communicator.receive_json_from(timeout=3)
        assert message["type"] == "supervision.snapshot"
        assert message["payload"]["scope"]["restricted"] is True
        assert [device["slot_id"] for device in message["payload"]["devices"]] == ["slot-assigned"]

        await communicator.disconnect()

    asyncio.run(scenario())


@pytest.mark.django_db(transaction=True)
def test_technician_supervision_websocket_rejects_unassigned_regular_user(user):
    token = str(RefreshToken.for_user(user).access_token)

    async def scenario():
        communicator = WebsocketCommunicator(
            application,
            f"/ws/technician/supervision/?token={token}",
            headers=[(b"host", b"localhost"), (b"origin", b"http://localhost")],
        )
        connected, _ = await communicator.connect()
        assert connected is False

    asyncio.run(scenario())
