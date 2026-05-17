import pytest
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
