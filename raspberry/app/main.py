from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import threading
import time
from urllib.parse import urlencode
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mqtt_client import publish_slot_command
from offline_store import OfflineStore
from rfid_reader import build_rfid_runtime

RFID_SCAN_STORE, RFID_RUNTIME = build_rfid_runtime()
OFFLINE_STORE = OfflineStore()
BACKEND_API_BASE_URL = os.environ.get("BACKEND_API_BASE_URL", "http://backend:8000/api").rstrip("/")
TERMINAL_API_SECRET = os.environ.get("TERMINAL_API_SECRET", "").strip()
TERMINAL_STATION_ID = os.environ.get("TERMINAL_STATION_ID", "").strip()
TERMINAL_BORNE_ID = os.environ.get("TERMINAL_BORNE_ID", "").strip()
OFFLINE_SYNC_INTERVAL_SECONDS = int(os.environ.get("OFFLINE_SYNC_INTERVAL_SECONDS", "60"))
OFFLINE_EVENT_BATCH_SIZE = int(os.environ.get("OFFLINE_EVENT_BATCH_SIZE", "50"))
TERMINAL_PROXY_ROUTES = {
    "/backend-api/terminal/authenticate/": "authenticate",
    "/backend-api/terminal/link-rfid/": "link_rfid",
    "/backend-api/terminal/mobile-sessions/": "mobile_sessions_create",
    "/backend-api/terminal/mobile-sessions/status/": "mobile_sessions_status",
    "/backend-api/terminal/mobile-sessions/consume/": "mobile_sessions_consume",
    "/backend-api/terminal/sessions/stop/": "sessions_stop",
}
TERMINAL_BACKEND_PATHS = {
    "authenticate": "/terminal/authenticate/",
    "link_rfid": "/terminal/link-rfid/",
    "mobile_sessions_create": "/terminal/mobile-sessions/",
    "mobile_sessions_status": "/terminal/mobile-sessions/status/",
    "mobile_sessions_consume": "/terminal/mobile-sessions/consume/",
    "sessions_stop": "/terminal/sessions/stop/",
}


def backend_headers(extra=None):
    """Return headers shared by Raspberry-to-backend calls."""
    headers = dict(extra or {})
    if TERMINAL_API_SECRET:
        headers["X-Terminal-Secret"] = TERMINAL_API_SECRET
    return headers


def terminal_proxy_route(local_path):
    """Return the constant backend route key allowed for one kiosk path."""
    return TERMINAL_PROXY_ROUTES.get(local_path)


def proxy_backend_json(method, route_key, payload=None):
    """Forward one allowed kiosk call to the backend with the terminal secret."""
    backend_path = TERMINAL_BACKEND_PATHS.get(route_key)
    if backend_path is None:
        return {
            "body": json.dumps({"detail": "Chemin API locale refuse."}).encode("utf-8"),
            "status": 404,
            "content_type": "application/json",
        }

    body = None
    headers = {"Accept": "application/json"}
    if method in {"POST", "PATCH", "PUT"}:
        body = json.dumps(payload or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(
        f"{BACKEND_API_BASE_URL}{backend_path}",
        data=body,
        headers=backend_headers(headers),
        method=method,
    )
    try:
        with urlopen(request, timeout=8) as response:
            response_body = response.read()
            status_code = response.status
            content_type = response.headers.get("Content-Type") or "application/json"
    except HTTPError as error:
        response_body = error.read()
        status_code = error.code
        content_type = error.headers.get("Content-Type") or "application/json"
    except URLError as error:
        return {
            "body": json.dumps({"detail": f"Backend indisponible: {error.reason}"}).encode("utf-8"),
            "status": 503,
            "content_type": "application/json",
        }

    return {
        "body": response_body or b"{}",
        "status": status_code,
        "content_type": content_type,
    }


def sync_offline_cache():
    """Pull near-term reservations from the backend into the local SQLite cache."""
    query_params = {
        key: value
        for key, value in {
            "station_id": TERMINAL_STATION_ID,
            "borne_id": TERMINAL_BORNE_ID,
        }.items()
        if value
    }
    query = urlencode(query_params) if query_params else ""
    url = f"{BACKEND_API_BASE_URL}/terminal/offline-cache/{f'?{query}' if query else ''}"
    request = Request(url, headers=backend_headers({"Accept": "application/json"}))
    with urlopen(request, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
    reservations = payload.get("results") or []
    OFFLINE_STORE.configure_grace_periods(
        start_minutes=payload.get("start_grace_minutes"),
        end_minutes=payload.get("end_grace_minutes"),
    )
    cached = OFFLINE_STORE.replace_reservations(reservations, station_id=TERMINAL_STATION_ID)
    return {
        "cached": cached,
        "generated_at": payload.get("generated_at"),
        "expires_at": payload.get("expires_at"),
        "station_id": payload.get("station_id") or TERMINAL_STATION_ID,
        "start_grace_minutes": payload.get("start_grace_minutes"),
        "end_grace_minutes": payload.get("end_grace_minutes"),
    }


def sync_offline_events():
    """Push locally accepted offline events back to the backend."""
    events = OFFLINE_STORE.pending_events(limit=OFFLINE_EVENT_BATCH_SIZE)
    if not events:
        return {"sent": 0, "synced": 0, "rejected": []}

    payload = {
        "station_id": TERMINAL_STATION_ID,
        "borne_id": TERMINAL_BORNE_ID,
        "events": events,
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{BACKEND_API_BASE_URL}/terminal/offline-events/",
        data=body,
        headers=backend_headers({
            "Accept": "application/json",
            "Content-Type": "application/json",
        }),
        method="POST",
    )
    with urlopen(request, timeout=8) as response:
        result = json.loads(response.read().decode("utf-8"))

    synced_ids = result.get("synced_event_ids") or []
    marked = OFFLINE_STORE.mark_events_synced(synced_ids)
    return {
        "sent": len(events),
        "synced": marked,
        "rejected": result.get("rejected") or [],
    }


def background_offline_sync():
    """Periodically refresh the degraded-mode cache while the backend is reachable."""
    while True:
        try:
            event_result = sync_offline_events()
            if event_result["sent"]:
                print(
                    "Offline events synced: "
                    f"{event_result['synced']}/{event_result['sent']} accepted"
                )
            result = sync_offline_cache()
            print(f"Offline cache synced: {result['cached']} reservations")
        except Exception as error:  # noqa: BLE001 - kiosk must keep running offline.
            print(f"Offline cache sync failed: {error}")
        time.sleep(OFFLINE_SYNC_INTERVAL_SECONDS)


class KioskHandler(SimpleHTTPRequestHandler):
    """Serve the kiosk UI and expose local edge endpoints."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_proxy(self, proxy_response):
        body = proxy_response["body"]
        self.send_response(proxy_response["status"])
        self.send_header("Content-Type", proxy_response["content_type"])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def do_POST(self):
        """Handle local Raspberry edge actions."""

        parsed_path = urlparse(self.path)
        proxy_route = terminal_proxy_route(parsed_path.path)
        if proxy_route:
            try:
                payload = self._read_json()
            except json.JSONDecodeError:
                self._send_json({"detail": "JSON invalide."}, status=400)
                return
            self._send_proxy(proxy_backend_json("POST", proxy_route, payload))
            return

        if parsed_path.path == "/rfid/scan":
            try:
                payload = self._read_json()
                uid = payload.get("uid") or payload.get("auth_value") or ""
                scan, accepted = RFID_SCAN_STORE.register(uid, source="api")
            except json.JSONDecodeError:
                self._send_json({"detail": "JSON invalide."}, status=400)
                return
            except ValueError as error:
                self._send_json({"detail": str(error)}, status=400)
                return

            self._send_json(
                {
                    "message": "Scan RFID recu." if accepted else "Scan RFID ignore par debounce.",
                    "accepted": accepted,
                    "scan": scan.to_dict() if scan else None,
                },
                status=201 if accepted else 200,
            )
            return

        if parsed_path.path == "/offline/sync":
            try:
                events_result = sync_offline_events()
                cache_result = sync_offline_cache()
                self._send_json(
                    {
                        "message": "Mode degrade synchronise.",
                        "events": events_result,
                        "cache": cache_result,
                    }
                )
            except Exception as error:  # noqa: BLE001
                self._send_json({"detail": f"Synchronisation offline impossible: {error}"}, status=503)
            return

        if parsed_path.path == "/offline/events/sync":
            try:
                self._send_json({"message": "Evenements offline synchronises.", **sync_offline_events()})
            except Exception as error:  # noqa: BLE001
                self._send_json({"detail": f"Synchronisation evenements offline impossible: {error}"}, status=503)
            return

        if parsed_path.path == "/offline/authenticate":
            try:
                payload = self._read_json()
                station_id = str(payload.get("station_id") or TERMINAL_STATION_ID).strip()
                borne_id = str(payload.get("borne_id") or TERMINAL_BORNE_ID).strip()
                result = OFFLINE_STORE.authenticate(payload, station_id=station_id, borne_id=borne_id)
            except json.JSONDecodeError:
                self._send_json({"detail": "JSON invalide."}, status=400)
                return
            except ValueError as error:
                self._send_json({"detail": str(error), "offline": True}, status=401)
                return

            self._send_json(result.to_payload())
            return

        if parsed_path.path != "/mqtt/command":
            self._send_json({"detail": "Endpoint introuvable."}, status=404)
            return

        try:
            payload = self._read_json()
            slot_id = str(payload.get("slot_id") or "").strip()
            action = str(payload.get("action") or "").strip().upper()
            if not slot_id or action not in {"START", "STOP", "LOCK", "UNLOCK"}:
                self._send_json({"detail": "slot_id et action MQTT valide sont obligatoires."}, status=400)
                return

            command_result = publish_slot_command(
                slot_id,
                action,
                command_id=payload.get("command_id") or "",
                session_id=payload.get("session_id") or "",
                station=payload.get("station") or "",
                borne=payload.get("borne") or "",
                emplacement=payload.get("emplacement") or "",
                source="raspberry",
            )
        except json.JSONDecodeError:
            self._send_json({"detail": "JSON invalide."}, status=400)
            return
        except RuntimeError as error:
            self._send_json({"detail": str(error)}, status=503)
            return
        except OSError as error:
            self._send_json({"detail": f"Broker MQTT indisponible: {error}"}, status=503)
            return

        if command_result.get("ack_received") and not command_result.get("command_confirmed"):
            self._send_json(
                {
                    "detail": "ACK ESP32 recu mais non confirmant.",
                    "mqtt": command_result,
                },
                status=409,
            )
            return

        message = (
            "Commande MQTT confirmee par ESP32."
            if command_result.get("command_confirmed")
            else "Commande MQTT envoyee."
        )
        self._send_json({"message": message, "mqtt": command_result})

    def do_GET(self):
        """Expose local Raspberry status endpoints and static files."""

        parsed_path = urlparse(self.path)
        proxy_route = terminal_proxy_route(parsed_path.path)
        if proxy_route:
            self._send_proxy(proxy_backend_json("GET", proxy_route))
            return

        if parsed_path.path == "/rfid/status":
            self._send_json(RFID_RUNTIME.snapshot())
            return

        if parsed_path.path == "/offline/status":
            self._send_json(
                {
                    "backend_api_base_url": BACKEND_API_BASE_URL,
                    "station_id": TERMINAL_STATION_ID,
                    "borne_id": TERMINAL_BORNE_ID,
                    **OFFLINE_STORE.stats(),
                }
            )
            return

        if parsed_path.path == "/rfid/scan":
            query = parse_qs(parsed_path.query)
            try:
                since = int((query.get("since") or ["0"])[0] or "0")
            except ValueError:
                since = 0

            scan = RFID_SCAN_STORE.latest_after(since)
            if scan is None:
                self._send_json({"scan": None})
                return
            self._send_json({"scan": scan.to_dict()})
            return

        super().do_GET()


def main():
    os.chdir(Path(__file__).resolve().parent)
    threading.Thread(target=background_offline_sync, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 9000), KioskHandler)
    print("Kiosk server running on http://localhost:9000")
    print(f"RFID backend: {RFID_RUNTIME.status} ({RFID_RUNTIME.detail})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping kiosk server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
