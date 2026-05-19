from django.test import override_settings

from api.services.sms_access_policy import (
    sms_access_code_entropy_bits,
    sms_access_code_policy_payload,
    validate_sms_access_code_policy,
)


def test_sms_access_code_policy_matches_matrix_keypad_security_target():
    """Use an 8-character 0-9/A-D code compatible with a 4x4 keypad."""
    assert sms_access_code_policy_payload() == {
        "alphabet": "0123456789ABCD",
        "alphabet_size": 14,
        "length": 8,
        "max_attempts": 5,
        "input_device": "matrix_keypad_4x4",
        "combinations": 14**8,
        "entropy_bits": 30.46,
    }
    assert sms_access_code_entropy_bits() == 30.46
    assert validate_sms_access_code_policy() == []


@override_settings(SMS_ACCESS_CODE_LENGTH=4)
def test_sms_access_code_policy_rejects_short_codes():
    """Reject 4-character SMS codes because the brute-force space is too small."""
    assert ("api.E013", "SMS_ACCESS_CODE_LENGTH must be at least 8 characters.") in (
        validate_sms_access_code_policy()
    )


@override_settings(SMS_ACCESS_CODE_ALPHABET="0123456789ABCDEF")
def test_sms_access_code_policy_rejects_non_keypad_alphabet():
    """Keep generated codes typeable on the physical matrix keypad."""
    assert (
        "api.E011",
        "SMS_ACCESS_CODE_ALPHABET must only use the matrix keypad "
        "characters 0-9 and A-D.",
    ) in validate_sms_access_code_policy()


@override_settings(SMS_ACCESS_CODE_MAX_ATTEMPTS=6)
def test_sms_access_code_policy_rejects_too_many_attempts():
    """Keep online brute-force attempts bounded."""
    assert ("api.E014", "SMS_ACCESS_CODE_MAX_ATTEMPTS must be between 1 and 5.") in (
        validate_sms_access_code_policy()
    )
