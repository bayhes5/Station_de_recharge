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

from charge_state import ChargeStateError, ChargeStateStore
from mqtt_client import build_slot_monitor, publish_slot_command
from offline_store import OfflineStore
from rfid_reader import build_rfid_runtime

RFID_SCAN_STORE, RFID_RUNTIME = build_rfid_runtime()
OFFLINE_STORE = OfflineStore()
CHARGE_STATE_STORE = ChargeStateStore()
MQTT_SLOT_MONITOR = build_slot_monitor()
BACKEND_API_BASE_URL = os.environ.get("BACKEND_API_BASE_URL", "http://backend:8000/api").rstrip("/")
MOBILE_FRONTEND_BASE_URL = os.environ.get("MOBILE_FRONTEND_BASE_URL", "").strip().rstrip("/")
TERMINAL_API_SECRET = os.environ.get("TERMINAL_API_SECRET", "").strip()
TERMINAL_CODE = os.environ.get("TERMINAL_CODE", "").strip()
TERMINAL_STATION_ID = os.environ.get("TERMINAL_STATION_ID", "").strip()
TERMINAL_BORNE_ID = os.environ.get("TERMINAL_BORNE_ID", "").strip()
TERMINAL_CONFIG_PATH = Path(os.environ.get("TERMINAL_CONFIG_PATH", "terminal_config.json"))
TERMINAL_CONFIG = {}
KIOSK_PORT = int(os.environ.get("KIOSK_PORT", "9000"))
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
    if TERMINAL_CODE:
        headers["X-Terminal-Code"] = TERMINAL_CODE
    return headers


def apply_terminal_config(config):
    """Apply a backend-provisioned terminal identity to the local kiosk process."""
    global TERMINAL_BORNE_ID, TERMINAL_CONFIG, TERMINAL_STATION_ID

    if not isinstance(config, dict):
        return False
    station_id = str(config.get("station_id") or "").strip()
    borne_id = str(config.get("borne_id") or "").strip()
    if not station_id or not borne_id:
        return False

    TERMINAL_STATION_ID = station_id
    TERMINAL_BORNE_ID = borne_id
    TERMINAL_CONFIG = dict(config)
    return True


def save_terminal_config(config):
    """Persist the current terminal identity for degraded-mode restarts."""
    TERMINAL_CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_cached_terminal_config():
    """Restore the last known terminal identity when the backend is unavailable."""
    if not TERMINAL_CONFIG_PATH.exists():
        return False
    try:
        config = json.loads(TERMINAL_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return apply_terminal_config(config)


def refresh_terminal_config():
    """Fetch the station/borne identity linked to TERMINAL_CODE from the backend."""
    if not TERMINAL_CODE:
        return {
            "configured": bool(TERMINAL_STATION_ID and TERMINAL_BORNE_ID),
            "source": "environment",
            "station_id": TERMINAL_STATION_ID,
            "borne_id": TERMINAL_BORNE_ID,
        }

    query = urlencode({"terminal_code": TERMINAL_CODE})
    request = Request(
        f"{BACKEND_API_BASE_URL}/terminal/config/?{query}",
        headers=backend_headers({"Accept": "application/json"}),
    )
    with urlopen(request, timeout=8) as response:
        config = json.loads(response.read().decode("utf-8"))
    if not apply_terminal_config(config):
        raise RuntimeError("Configuration terminal incomplète reçue du backend.")
    save_terminal_config(config)
    return {"configured": True, "source": "backend", **config}


def current_terminal_config():
    """Return the active kiosk identity used for all terminal calls."""
    return {
        **TERMINAL_CONFIG,
        "terminal_code": TERMINAL_CONFIG.get("terminal_code") or TERMINAL_CODE,
        "station_id": TERMINAL_STATION_ID,
        "borne_id": TERMINAL_BORNE_ID,
        "source": "backend" if TERMINAL_CONFIG else "environment",
    }


def enrich_terminal_payload(payload):
    """Force the backend payload to use the provisioned kiosk identity."""
    enriched = dict(payload or {})
    if TERMINAL_STATION_ID:
        enriched["station_id"] = TERMINAL_STATION_ID
    if TERMINAL_BORNE_ID:
        enriched["borne_id"] = TERMINAL_BORNE_ID
    return enriched


def terminal_proxy_route(local_path):
    """Return the constant backend route key allowed for one kiosk path."""
    return TERMINAL_PROXY_ROUTES.get(local_path)


def proxy_backend_json(method, route_key, payload=None):
    """Forward one allowed kiosk call to the backend with the terminal secret."""
    backend_path = TERMINAL_BACKEND_PATHS.get(route_key)
    if backend_path is None:
        return {
            "body": json.dumps({"detail": "Chemin API locale refusé."}).encode("utf-8"),
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
    if TERMINAL_CODE:
        refresh_terminal_config()
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
    if TERMINAL_CODE:
        refresh_terminal_config()

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

    def _send_index(self):
        """Serve the kiosk page with runtime configuration injected."""
        index_path = Path(__file__).resolve().parent / "index.html"
        html = index_path.read_text(encoding="utf-8")
        runtime_config = (
            "<script>"
            f"window.__MOBILE_FRONTEND_BASE_URL__ = {json.dumps(MOBILE_FRONTEND_BASE_URL)};"
            "</script>"
        )
        html = html.replace('<script defer src="app.js"></script>', f"{runtime_config}\n    <script defer src=\"app.js\"></script>")
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
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
                payload = enrich_terminal_payload(self._read_json())
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
                        "message": "Mode dégradé synchronisé.",
                        "events": events_result,
                        "cache": cache_result,
                    }
                )
            except Exception as error:  # noqa: BLE001
                self._send_json({"detail": f"Synchronisation offline impossible: {error}"}, status=503)
            return

        if parsed_path.path == "/offline/events/sync":
            try:
                self._send_json({"message": "Événements offline synchronisés.", **sync_offline_events()})
            except Exception as error:  # noqa: BLE001
                self._send_json({"detail": f"Synchronisation evenements offline impossible: {error}"}, status=503)
            return

        if parsed_path.path == "/offline/authenticate":
            try:
                payload = enrich_terminal_payload(self._read_json())
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

        if parsed_path.path == "/charge/state/reset":
            technician_secret = self.headers.get("X-Terminal-Secret", "").strip()
            if TERMINAL_API_SECRET and technician_secret != TERMINAL_API_SECRET:
                self._send_json({"detail": "Opération technicien refusée."}, status=403)
                return
            try:
                payload = self._read_json()
                slot_id = str(payload.get("slot_id") or "").strip()
                if not slot_id:
                    self._send_json({"detail": "slot_id obligatoire."}, status=400)
                    return
                snapshot = CHARGE_STATE_STORE.reset_slot(
                    slot_id=slot_id,
                    detail="Etat local reinitialise par un technicien.",
                )
            except json.JSONDecodeError:
                self._send_json({"detail": "JSON invalide."}, status=400)
                return
            except ChargeStateError as error:
                self._send_json({"detail": str(error)}, status=400)
                return
            self._send_json(
                {
                    "message": "Etat local de charge reinitialise.",
                    "charge_state": snapshot.to_dict(),
                }
            )
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
            session_id = str(payload.get("session_id") or "").strip()
        except json.JSONDecodeError:
            self._send_json({"detail": "JSON invalide."}, status=400)
            return

        tracked_charge_command = action in {"START", "STOP"}
        if tracked_charge_command:
            try:
                if action == "START":
                    CHARGE_STATE_STORE.start_requested(
                        slot_id=slot_id,
                        session_id=session_id,
                        station=payload.get("station") or "",
                        borne=payload.get("borne") or "",
                        emplacement=payload.get("emplacement") or "",
                    )
                else:
                    CHARGE_STATE_STORE.stop_requested(
                        slot_id=slot_id,
                        session_id=session_id,
                    )
            except ChargeStateError as error:
                self._send_json(
                    {
                        "detail": str(error),
                        "charge_state": CHARGE_STATE_STORE.snapshot(slot_id).to_dict(),
                    },
                    status=409,
                )
                return

        try:
            command_result = publish_slot_command(
                slot_id,
                action,
                topic_prefix=payload.get("topic_prefix") or payload.get("mqtt_prefix") or "",
                command_id=payload.get("command_id") or "",
                session_id=session_id,
                station=payload.get("station") or "",
                borne=payload.get("borne") or "",
                emplacement=payload.get("emplacement") or "",
                source="raspberry",
            )
        except RuntimeError as error:
            response = {"detail": str(error)}
            if tracked_charge_command:
                response["charge_state"] = CHARGE_STATE_STORE.mark_error(
                    slot_id=slot_id,
                    session_id=session_id,
                    detail=f"Commande MQTT {action} en erreur: {error}",
                ).to_dict()
            self._send_json(response, status=503)
            return
        except OSError as error:
            response = {"detail": f"Broker MQTT indisponible: {error}"}
            if tracked_charge_command:
                response["charge_state"] = CHARGE_STATE_STORE.mark_error(
                    slot_id=slot_id,
                    session_id=session_id,
                    detail=f"Broker MQTT indisponible pendant {action}: {error}",
                ).to_dict()
            self._send_json(response, status=503)
            return

        charge_state = None
        if command_result.get("ack_received") and not command_result.get("command_confirmed"):
            if tracked_charge_command:
                charge_state = CHARGE_STATE_STORE.mark_error(
                    slot_id=slot_id,
                    session_id=session_id,
                    detail="ACK ESP32 recu mais non confirmant.",
                    payload=command_result,
                ).to_dict()
            self._send_json(
                {
                    "detail": "ACK ESP32 recu mais non confirmant.",
                    "mqtt": command_result,
                    "charge_state": charge_state,
                },
                status=409,
            )
            return

        if tracked_charge_command:
            charge_state = CHARGE_STATE_STORE.command_recorded(
                slot_id=slot_id,
                action=action,
                session_id=session_id,
                mqtt_result=command_result,
            ).to_dict()

        message = (
            "Commande MQTT confirmée par ESP32."
            if command_result.get("command_confirmed")
            else "Commande MQTT envoyee."
        )
        self._send_json(
            {
                "message": message,
                "mqtt": command_result,
                "charge_state": charge_state,
            }
        )

    def do_GET(self):
        """Expose local Raspberry status endpoints and static files."""

        parsed_path = urlparse(self.path)
        if parsed_path.path in {"", "/", "/index.html"}:
            self._send_index()
            return

        proxy_route = terminal_proxy_route(parsed_path.path)
        if proxy_route:
            self._send_proxy(proxy_backend_json("GET", proxy_route))
            return

        if parsed_path.path == "/rfid/status":
            self._send_json(RFID_RUNTIME.snapshot())
            return

        if parsed_path.path == "/terminal/config":
            if parsed_path.query == "refresh":
                try:
                    self._send_json(refresh_terminal_config())
                except Exception as error:  # noqa: BLE001
                    if load_cached_terminal_config():
                        self._send_json(
                            {
                                **current_terminal_config(),
                                "source": "cache",
                                "warning": f"Configuration backend indisponible: {error}",
                            },
                            status=200,
                        )
                    else:
                        self._send_json({"detail": f"Configuration terminal indisponible: {error}"}, status=503)
                return
            self._send_json(current_terminal_config())
            return

        if parsed_path.path == "/offline/status":
            self._send_json(
                {
                    "backend_api_base_url": BACKEND_API_BASE_URL,
                    **current_terminal_config(),
                    **OFFLINE_STORE.stats(),
                }
            )
            return

        if parsed_path.path == "/charge/state":
            query = parse_qs(parsed_path.query)
            slot_id = str((query.get("slot_id") or [""])[0] or "").strip()
            if slot_id:
                self._send_json({"result": CHARGE_STATE_STORE.snapshot(slot_id).to_dict()})
                return
            self._send_json(
                {
                    "results": [
                        snapshot.to_dict()
                        for snapshot in CHARGE_STATE_STORE.all_snapshots()
                    ]
                }
            )
            return

        if parsed_path.path == "/mqtt/slot-status":
            query = parse_qs(parsed_path.query)
            slot_id = str((query.get("slot_id") or [""])[0] or "").strip()
            if not slot_id:
                self._send_json({"detail": "slot_id obligatoire."}, status=400)
                return
            self._send_json({"result": MQTT_SLOT_MONITOR.snapshot(slot_id)})
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
    if TERMINAL_CODE:
        try:
            config = refresh_terminal_config()
            print(
                "Terminal provisioned: "
                f"{config.get('station')} / {config.get('borne')} "
                f"({TERMINAL_STATION_ID}/{TERMINAL_BORNE_ID})"
            )
        except Exception as error:  # noqa: BLE001 - kiosk must still boot offline.
            if load_cached_terminal_config():
                print(
                    "Terminal config restored from cache: "
                    f"{TERMINAL_STATION_ID}/{TERMINAL_BORNE_ID} "
                    f"(backend unavailable: {error})"
                )
            else:
                print(f"Terminal config unavailable: {error}")
    threading.Thread(target=background_offline_sync, daemon=True).start()
    MQTT_SLOT_MONITOR.start()
    server = ThreadingHTTPServer(("0.0.0.0", KIOSK_PORT), KioskHandler)
    print(f"Kiosk server running on http://localhost:{KIOSK_PORT}")
    print(f"RFID backend: {RFID_RUNTIME.status} ({RFID_RUNTIME.detail})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping kiosk server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
