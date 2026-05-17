from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import logging
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
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


def _setting(name):
    """Return one SMS setting as stripped text."""
    return str(getattr(settings, name, "") or "").strip()


def _require_settings(*names):
    """Return required SMS settings or raise a delivery error."""
    values = {name: _setting(name) for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SmsDeliveryError(f"Configuration SMS manquante: {', '.join(missing)}.")
    return values


def _open_http_json(request, *, expected_statuses=(200, 201, 202)):
    """Execute a JSON HTTP request and return the decoded response body."""
    try:
        with urlopen(request, timeout=getattr(settings, "SMS_HTTP_TIMEOUT_SECONDS", 10)) as response:
            body = response.read().decode("utf-8")
            if response.status not in expected_statuses:
                raise SmsDeliveryError(f"Provider SMS a répondu HTTP {response.status}.")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise SmsDeliveryError(f"Provider SMS a refusé la requête HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise SmsDeliveryError(f"Provider SMS injoignable: {error.reason}") from error

    if not body:
        return {}
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise SmsDeliveryError("Provider SMS a renvoyé une réponse JSON invalide.") from error


def _send_twilio_sms(phone_number, message):
    """Send a SMS through Twilio Programmable Messaging."""
    values = _require_settings("SMS_TWILIO_ACCOUNT_SID", "SMS_TWILIO_AUTH_TOKEN", "SMS_TWILIO_FROM")
    account_sid = values["SMS_TWILIO_ACCOUNT_SID"]
    auth_token = values["SMS_TWILIO_AUTH_TOKEN"]
    body = urlencode(
        {
            "To": phone_number,
            "From": values["SMS_TWILIO_FROM"],
            "Body": message,
        }
    ).encode("utf-8")
    auth = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    request = Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
        data=body,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    response = _open_http_json(request, expected_statuses=(200, 201))
    return SmsResult(backend="twilio", message_id=str(response.get("sid") or uuid.uuid4()))


def _send_brevo_sms(phone_number, message):
    """Send a SMS through Brevo transactional SMS."""
    values = _require_settings("SMS_BREVO_API_KEY", "SMS_SENDER_NAME")
    payload = json.dumps(
        {
            "sender": values["SMS_SENDER_NAME"][:11],
            "recipient": phone_number,
            "content": message,
            "type": "transactional",
        }
    ).encode("utf-8")
    request = Request(
        "https://api.brevo.com/v3/transactionalSMS/sms",
        data=payload,
        headers={
            "api-key": values["SMS_BREVO_API_KEY"],
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    response = _open_http_json(request, expected_statuses=(200, 201, 202))
    return SmsResult(backend="brevo", message_id=str(response.get("messageId") or uuid.uuid4()))


def _send_ovh_sms(phone_number, message):
    """Reject OVH SMS until a hardened adapter replaces its legacy SHA-1 signing."""
    raise SmsDeliveryError(
        "Backend SMS OVH non active dans le profil durci: utiliser console, twilio ou brevo."
    )


def send_sms(phone_number, message):
    """Send a SMS through the configured backend.

    The development backend logs the message locally. A production provider can
    be wired behind this function without changing reservation workflows.
    """
    backend = getattr(settings, "SMS_BACKEND", "console").strip().lower()
    if not str(phone_number or "").strip():
        raise SmsDeliveryError("Numéro de téléphone absent.")

    if backend == "disabled":
        raise SmsDeliveryError("Envoi SMS désactivé.")

    if backend == "console":
        message_id = f"console-{uuid.uuid4()}"
        logger.info(
            "SMS console delivery id=%s length=%s",
            message_id,
            len(str(message or "")),
        )
        return SmsResult(backend=backend, message_id=message_id)

    if backend == "twilio":
        return _send_twilio_sms(phone_number, message)
    if backend == "brevo":
        return _send_brevo_sms(phone_number, message)
    if backend == "ovh":
        return _send_ovh_sms(phone_number, message)

    raise SmsDeliveryError(f"Backend SMS non configuré: {backend}.")
