import asyncio

import pytest
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import RefreshToken

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
