"""RFID scan helpers for the Raspberry kiosk.

The kiosk can receive UIDs from a real reader later, but the rest of the
application only needs a small debounced event stream.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import os
import sys
import threading
import time


def normalize_uid(value):
    """Return a stable display/storage form for one RFID UID."""
    return "".join(char for char in str(value or "").strip().upper() if char.isalnum())


@dataclass(frozen=True)
class RfidScan:
    """One RFID scan event exposed to the kiosk frontend."""

    id: int
    uid: str
    source: str
    timestamp: float

    def to_dict(self):
        payload = asdict(self)
        payload["timestamp_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.timestamp))
        return payload


class RfidScanStore:
    """Keep the latest RFID scan and ignore accidental duplicate reads."""

    def __init__(self, debounce_seconds=2.0):
        self.debounce_seconds = float(debounce_seconds)
        self._lock = threading.Lock()
        self._last_scan = None
        self._last_seen = {}
        self._next_id = 1

    def register(self, uid, source="manual"):
        normalized_uid = normalize_uid(uid)
        if not normalized_uid:
            raise ValueError("UID RFID vide.")

        now = time.time()
        with self._lock:
            last_timestamp = self._last_seen.get(normalized_uid)
            if last_timestamp is not None and now - last_timestamp < self.debounce_seconds:
                return self._last_scan, False

            scan = RfidScan(
                id=self._next_id,
                uid=normalized_uid,
                source=source,
                timestamp=now,
            )
            self._next_id += 1
            self._last_scan = scan
            self._last_seen[normalized_uid] = now
            return scan, True

    def latest_after(self, scan_id):
        with self._lock:
            if self._last_scan is None or self._last_scan.id <= scan_id:
                return None
            return self._last_scan


class RfidReaderRuntime:
    """Start an optional background reader for local Raspberry hardware."""

    def __init__(self, store, backend="disabled"):
        self.store = store
        self.backend = (backend or "disabled").strip().lower()
        self.status = "disabled"
        self.detail = ""
        self._thread = None

    def start(self):
        if self.backend in {"", "disabled", "manual"}:
            self.status = "manual"
            self.detail = "Lecture automatique desactivee; endpoint /rfid/scan disponible."
            return

        if self.backend == "stdin":
            self.status = "running"
            self.detail = "Lecture RFID depuis stdin."
            self._thread = threading.Thread(target=self._stdin_loop, daemon=True)
            self._thread.start()
            return

        if self.backend == "nfcpy":
            self.status = "starting"
            self.detail = "Lecture RFID via nfcpy."
            self._thread = threading.Thread(target=self._nfcpy_loop, daemon=True)
            self._thread.start()
            return

        if self.backend in {"acr122u", "pcsc"}:
            self.status = "starting"
            self.detail = "Lecture RFID via PC/SC ACR122U."
            self._thread = threading.Thread(target=self._pcsc_loop, daemon=True)
            self._thread.start()
            return

        self.status = "error"
        self.detail = f"Backend RFID inconnu: {self.backend}."

    def snapshot(self):
        return {
            "backend": self.backend,
            "status": self.status,
            "detail": self.detail,
            "debounce_seconds": self.store.debounce_seconds,
        }

    def _stdin_loop(self):
        for line in sys.stdin:
            try:
                self.store.register(line, source="stdin")
            except ValueError:
                continue

    def _nfcpy_loop(self):
        try:
            import nfc
        except ImportError:
            self.status = "error"
            self.detail = "nfcpy n'est pas installe sur le Raspberry."
            return

        def on_connect(tag):
            uid = getattr(tag, "identifier", b"")
            if isinstance(uid, bytes):
                uid = uid.hex().upper()
            self.store.register(uid, source="nfcpy")
            return False

        while True:
            try:
                with nfc.ContactlessFrontend("usb") as clf:
                    self.status = "running"
                    self.detail = "Lecteur NFC USB pret."
                    clf.connect(rdwr={"on-connect": on_connect})
            except OSError as error:
                self.status = "error"
                self.detail = f"Lecteur NFC indisponible: {error}"
                time.sleep(5)

    def _pcsc_loop(self):
        try:
            from smartcard.CardRequest import CardRequest
            from smartcard.Exceptions import CardRequestTimeoutException, NoCardException
            from smartcard.System import readers
            from smartcard.util import toHexString
        except ImportError:
            self.status = "error"
            self.detail = "pyscard n'est pas installe pour le lecteur ACR122U."
            return

        while True:
            try:
                available_readers = readers()
                if not available_readers:
                    self.status = "error"
                    self.detail = "Lecteur ACR122U introuvable via PC/SC."
                    time.sleep(5)
                    continue

                reader = available_readers[0]
                self.status = "running"
                self.detail = f"Lecteur PC/SC pret: {reader}."
                card_request = CardRequest(timeout=1, readers=[reader])
                card_service = card_request.waitforcard()
                card_service.connection.connect()

                data, sw1, sw2 = card_service.connection.transmit([0xFF, 0xCA, 0x00, 0x00, 0x00])
                if (sw1, sw2) == (0x90, 0x00) and data:
                    uid = toHexString(data).replace(" ", "")
                    self.store.register(uid, source="acr122u")

                time.sleep(self.store.debounce_seconds)
            except CardRequestTimeoutException:
                continue
            except NoCardException:
                continue
            except Exception as error:
                self.status = "error"
                self.detail = f"Erreur lecteur ACR122U: {error}"
                time.sleep(5)


def build_rfid_runtime():
    debounce = float(os.environ.get("RFID_DEBOUNCE_SECONDS", "2"))
    backend = os.environ.get("RFID_READER_BACKEND", "manual")
    store = RfidScanStore(debounce_seconds=debounce)
    runtime = RfidReaderRuntime(store, backend=backend)
    runtime.start()
    return store, runtime
