from __future__ import annotations

from dataclasses import dataclass
import logging
import uuid

from django.conf import settings


logger = logging.getLogger(__name__)


class SmsDeliveryError(RuntimeError):
    """Raised when the configured SMS backend cannot deliver a message."""


@dataclass(frozen=True)
class SmsResult:
    """Describe a SMS delivery attempt."""

    backend: str
    message_id: str


def mask_phone_number(phone_number):
    """Return a display-safe phone hint."""
    raw = str(phone_number or "").strip()
    digits = "".join(char for char in raw if char.isdigit())
    if not digits:
        return ""
    return f"******{digits[-4:]}"


def send_sms(phone_number, message):
    """Send a SMS through the configured backend.

    The development backend logs the message locally. A production provider can
    be wired behind this function without changing reservation workflows.
    """
    backend = getattr(settings, "SMS_BACKEND", "console").strip().lower()
    if not str(phone_number or "").strip():
        raise SmsDeliveryError("Numero de telephone absent.")

    if backend == "disabled":
        raise SmsDeliveryError("Envoi SMS desactive.")

    if backend == "console":
        message_id = f"console-{uuid.uuid4()}"
        logger.info(
            "SMS console to %s: %s",
            mask_phone_number(phone_number),
            message,
        )
        return SmsResult(backend=backend, message_id=message_id)

    raise SmsDeliveryError(f"Backend SMS non configure: {backend}.")
