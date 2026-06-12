import pytest
from django.core import mail
from django.test import override_settings

from api.services.sms import SmsDeliveryError, SmsResult, mask_phone_number, send_sms


def test_mask_phone_number_only_exposes_last_digits():
    """Mask phone numbers before returning delivery hints to clients."""
    assert mask_phone_number("+33 6 00 00 00 00") == "******0000"
    assert mask_phone_number("") == ""


@override_settings(SMS_BACKEND="console")
def test_console_sms_backend_returns_delivery_result():
    """Use the console backend for local development without external provider."""
    result = send_sms("+33600000000", "Code 1234")

    assert isinstance(result, SmsResult)
    assert result.backend == "console"
    assert result.message_id.startswith("console-")


@override_settings(SMS_BACKEND="email", DEFAULT_FROM_EMAIL="Station <no-reply@station.local>")
def test_email_sms_backend_sends_message_to_mail_backend():
    """Use the email backend to demonstrate SMS delivery through Mailpit."""
    result = send_sms(
        "+33600000000",
        "Votre code SMS temporaire est A1B2C3D4.",
        email_recipient="demo@example.com",
    )

    assert result.backend == "email"
    assert result.message_id.startswith("email-")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["demo@example.com"]
    assert "A1B2C3D4" in mail.outbox[0].body


@override_settings(SMS_BACKEND="email", SMS_EMAIL_FALLBACK_RECIPIENT="fallback@example.com")
def test_email_sms_backend_can_use_fallback_recipient():
    """Allow development SMS e-mails when the caller has no direct e-mail argument."""
    result = send_sms("+33600000000", "Code fallback")

    assert result.backend == "email"
    assert mail.outbox[0].to == ["fallback@example.com"]


@pytest.mark.parametrize("backend", ["twilio", "brevo"])
def test_production_sms_backends_fail_fast_when_configuration_is_missing(settings, backend):
    """Fail before delivery when a production provider lacks credentials."""
    settings.SMS_BACKEND = backend

    with pytest.raises(SmsDeliveryError, match="Configuration SMS manquante"):
        send_sms("+33600000000", "Code 1234")


@override_settings(SMS_BACKEND="ovh")
def test_ovh_sms_backend_is_rejected_in_hardened_build():
    """Keep the hardened build free from OVH's legacy SHA-1 request signature."""
    with pytest.raises(SmsDeliveryError, match="OVH non active"):
        send_sms("+33600000000", "Code 1234")
