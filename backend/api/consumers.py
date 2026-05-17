from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from api.models import Technicien, TechnicienStation
from api.realtime import SUPERVISION_GROUP_NAME
from api.services.supervision import build_admin_supervision_payload


@database_sync_to_async
def _get_active_user(token_value: str | None):
    if not token_value:
        return None

    try:
        token = AccessToken(token_value)
    except (InvalidToken, TokenError):
        return None

    user_id = token.get("user_id")
    if not user_id:
        return None

    user_model = get_user_model()
    try:
        user = user_model.objects.get(pk=user_id)
    except user_model.DoesNotExist:
        return None

    if not user.is_active:
        return None
    return user


@database_sync_to_async
def _station_ids_for_user(user):
    """Return None for global staff scope or station ids for one technician."""
    if user.is_staff:
        return None

    try:
        technicien = user.technicien_profile
    except Technicien.DoesNotExist:
        return []

    return list(
        TechnicienStation.objects.filter(technicien=technicien, is_active=True)
        .order_by("station__nom")
        .values_list("station_id", flat=True)
    )


@database_sync_to_async
def _supervision_snapshot(station_ids=None):
    return build_admin_supervision_payload(station_ids=station_ids)


class AdminSupervisionConsumer(AsyncJsonWebsocketConsumer):
    """Push supervision snapshots to connected administrator dashboards."""

    async def connect(self):
        """Accept staff WebSocket clients and send the initial supervision snapshot."""
        query = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        token = query.get("token", [None])[0]
        self.user = await _get_active_user(token)
        if not self.user or not self.user.is_staff:
            await self.close(code=4401)
            return
        self.station_ids = None

        await self.accept()
        await self.channel_layer.group_add(SUPERVISION_GROUP_NAME, self.channel_name)
        await self._send_snapshot(reason="connected")

    async def disconnect(self, _close_code):
        """Remove the socket from the supervision group when it closes."""
        if getattr(self, "user", None):
            await self.channel_layer.group_discard(SUPERVISION_GROUP_NAME, self.channel_name)

    async def receive_json(self, content, **_kwargs):
        """Handle client refresh requests sent over the WebSocket."""
        if content.get("type") == "refresh":
            await self._send_snapshot(reason="manual-refresh")

    async def supervision_update(self, event):
        """Send a fresh snapshot after a backend supervision broadcast."""
        await self._send_snapshot(reason=event.get("reason", "update"), summary=event.get("summary") or {})

    async def _send_snapshot(self, reason: str, summary: dict | None = None):
        await self.send_json(
            {
                "type": "supervision.snapshot",
                "reason": reason,
                "summary": summary or {},
                "payload": await _supervision_snapshot(station_ids=self.station_ids),
            }
        )


class TechnicianSupervisionConsumer(AdminSupervisionConsumer):
    """Push scoped supervision snapshots to technician dashboards."""

    async def connect(self):
        """Accept technicians and staff, then scope snapshots by assignment."""
        query = parse_qs(self.scope.get("query_string", b"").decode("utf-8"))
        token = query.get("token", [None])[0]
        self.user = await _get_active_user(token)
        if not self.user:
            await self.close(code=4401)
            return

        self.station_ids = await _station_ids_for_user(self.user)
        if self.station_ids == [] and not self.user.is_staff:
            await self.close(code=4401)
            return

        await self.accept()
        await self.channel_layer.group_add(SUPERVISION_GROUP_NAME, self.channel_name)
        await self._send_snapshot(reason="connected")
