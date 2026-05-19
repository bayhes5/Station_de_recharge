"""Security policy for reservation SMS access codes."""

from __future__ import annotations

import math

from django.conf import settings

MATRIX_KEYPAD_ALPHABET = "0123456789ABCD"
DEFAULT_SMS_ACCESS_CODE_LENGTH = 8
DEFAULT_SMS_ACCESS_CODE_MAX_ATTEMPTS = 5
MIN_SMS_ACCESS_CODE_LENGTH = 8
MAX_SMS_ACCESS_CODE_ATTEMPTS = 5


def configured_sms_access_code_alphabet() -> str:
    """Return the configured alphabet, preserving keypad order."""
    configured = str(
        getattr(settings, "SMS_ACCESS_CODE_ALPHABET", MATRIX_KEYPAD_ALPHABET)
        or MATRIX_KEYPAD_ALPHABET
    ).upper()
    seen = set()
    alphabet = []
    for character in configured:
        if character in seen:
            continue
        seen.add(character)
        alphabet.append(character)
    return "".join(alphabet)


def configured_sms_access_code_length() -> int:
    """Return the configured SMS code length."""
    return int(
        getattr(settings, "SMS_ACCESS_CODE_LENGTH", DEFAULT_SMS_ACCESS_CODE_LENGTH)
        or DEFAULT_SMS_ACCESS_CODE_LENGTH
    )


def configured_sms_access_code_max_attempts() -> int:
    """Return the number of attempts allowed before a code is locked."""
    return int(
        getattr(
            settings,
            "SMS_ACCESS_CODE_MAX_ATTEMPTS",
            DEFAULT_SMS_ACCESS_CODE_MAX_ATTEMPTS,
        )
        or DEFAULT_SMS_ACCESS_CODE_MAX_ATTEMPTS
    )


def sms_access_code_combinations(
    length: int | None = None,
    alphabet: str | None = None,
) -> int:
    """Return the brute-force search space for the SMS code policy."""
    code_length = configured_sms_access_code_length() if length is None else int(length)
    code_alphabet = (
        configured_sms_access_code_alphabet() if alphabet is None else str(alphabet)
    )
    return len(code_alphabet) ** code_length


def sms_access_code_entropy_bits(
    length: int | None = None,
    alphabet: str | None = None,
) -> float:
    """Return the approximate entropy of the SMS code policy."""
    combinations = sms_access_code_combinations(length=length, alphabet=alphabet)
    return round(math.log2(combinations), 2) if combinations > 0 else 0.0


def sms_access_code_policy_payload() -> dict[str, object]:
    """Return a serializable policy summary safe to expose in API metadata."""
    alphabet = configured_sms_access_code_alphabet()
    length = configured_sms_access_code_length()
    return {
        "alphabet": alphabet,
        "alphabet_size": len(alphabet),
        "length": length,
        "max_attempts": configured_sms_access_code_max_attempts(),
        "input_device": "matrix_keypad_4x4",
        "combinations": sms_access_code_combinations(length=length, alphabet=alphabet),
        "entropy_bits": sms_access_code_entropy_bits(length=length, alphabet=alphabet),
    }


def validate_sms_access_code_policy() -> list[tuple[str, str]]:
    """Return deployment-check errors for an unsafe SMS code policy."""
    messages: list[tuple[str, str]] = []
    alphabet = configured_sms_access_code_alphabet()
    invalid_characters = sorted(set(alphabet) - set(MATRIX_KEYPAD_ALPHABET))
    if invalid_characters:
        messages.append(
            (
                "api.E011",
                "SMS_ACCESS_CODE_ALPHABET must only use the matrix keypad "
                "characters 0-9 and A-D.",
            )
        )
    if len(alphabet) < len(MATRIX_KEYPAD_ALPHABET):
        messages.append(
            (
                "api.E012",
                "SMS_ACCESS_CODE_ALPHABET should keep the full 0-9/A-D "
                "keypad alphabet.",
            )
        )
    if configured_sms_access_code_length() < MIN_SMS_ACCESS_CODE_LENGTH:
        messages.append(
            (
                "api.E013",
                "SMS_ACCESS_CODE_LENGTH must be at least 8 characters.",
            )
        )
    max_attempts = configured_sms_access_code_max_attempts()
    if max_attempts < 1 or max_attempts > MAX_SMS_ACCESS_CODE_ATTEMPTS:
        messages.append(
            (
                "api.E014",
                "SMS_ACCESS_CODE_MAX_ATTEMPTS must be between 1 and 5.",
            )
        )
    return messages
