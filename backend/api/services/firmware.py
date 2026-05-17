"""Firmware compliance helpers for ESP32 devices."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from api.models import Device, FirmwareUpdateStatus


NON_TERMINAL_UPDATE_STATES = {
    FirmwareUpdateStatus.UPDATE_SCHEDULED,
    FirmwareUpdateStatus.UPDATING,
}


def expected_firmware_version(device: Device) -> str:
    """Return the device-specific expected version or the global default."""
    device_expected = str(device.expected_firmware_version or "").strip()
    if device_expected:
        return device_expected
    return str(getattr(settings, "EXPECTED_ESP32_FIRMWARE_VERSION", "") or "").strip()


def firmware_update_required(device: Device) -> bool:
    """Return whether the reported firmware differs from the expected version."""
    expected = expected_firmware_version(device)
    current = str(device.firmware_version or "").strip()
    return bool(expected and current and current != expected)


def update_firmware_compliance_status(
    device: Device,
    *,
    timestamp=None,
    update_fields: list[str] | None = None,
):
    """Synchronize the stored firmware status with the last reported version."""
    expected = expected_firmware_version(device)
    current = str(device.firmware_version or "").strip()
    timestamp = timestamp or timezone.now()
    update_fields = update_fields if update_fields is not None else []

    if not expected or not current:
        next_status = FirmwareUpdateStatus.UNKNOWN
    elif current == expected:
        next_status = FirmwareUpdateStatus.UP_TO_DATE
    elif device.firmware_update_status in NON_TERMINAL_UPDATE_STATES:
        next_status = device.firmware_update_status
    else:
        next_status = FirmwareUpdateStatus.UPDATE_REQUIRED

    if device.firmware_update_status != next_status:
        device.firmware_update_status = next_status
        update_fields.append("firmware_update_status")

    if next_status == FirmwareUpdateStatus.UP_TO_DATE:
        if device.ota_completed_at is None or device.ota_target_version == current:
            device.ota_completed_at = timestamp
            update_fields.append("ota_completed_at")
        if device.ota_last_error:
            device.ota_last_error = ""
            update_fields.append("ota_last_error")

    return next_status


def schedule_ota_update(
    device: Device,
    *,
    target_version: str,
    update_url: str = "",
):
    """Record an admin-approved OTA update request for one ESP32."""
    target = str(target_version or "").strip()
    if not target:
        raise ValueError("La version cible du firmware est obligatoire.")

    device.expected_firmware_version = target
    device.ota_target_version = target
    device.ota_update_url = str(update_url or "").strip()
    device.ota_requested_at = timezone.now()
    device.ota_completed_at = None
    device.ota_last_error = ""
    device.firmware_update_status = FirmwareUpdateStatus.UPDATE_SCHEDULED
    device.save(
        update_fields=[
            "expected_firmware_version",
            "ota_target_version",
            "ota_update_url",
            "ota_requested_at",
            "ota_completed_at",
            "ota_last_error",
            "firmware_update_status",
        ]
    )
    return device
