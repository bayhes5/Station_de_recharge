from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

SUPERVISION_GROUP_NAME = "admin_supervision"


def broadcast_supervision_update(reason: str, summary: dict | None = None) -> None:
    """Notify connected admin dashboards that the supervision snapshot changed."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    try:
        async_to_sync(channel_layer.group_send)(
            SUPERVISION_GROUP_NAME,
            {
                "type": "supervision.update",
                "reason": reason,
                "summary": summary or {},
            },
        )
    except Exception:
        logger.exception("Impossible de diffuser la mise a jour de supervision.")
