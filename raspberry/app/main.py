from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import json
import os

from mqtt_client import publish_slot_command


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

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body) if body else {}

    def do_POST(self):
        """Handle local Raspberry edge actions."""

        if self.path != "/mqtt/command":
            self._send_json({"detail": "Endpoint introuvable."}, status=404)
            return

        try:
            payload = self._read_json()
            slot_id = str(payload.get("slot_id") or "").strip()
            action = str(payload.get("action") or "").strip().upper()
            if not slot_id or action not in {"START", "STOP", "LOCK", "UNLOCK"}:
                self._send_json({"detail": "slot_id et action MQTT valide sont obligatoires."}, status=400)
                return

            command_payload = publish_slot_command(
                slot_id,
                action,
                session_id=payload.get("session_id") or "",
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

        self._send_json({"message": "Commande MQTT envoyee.", "payload": command_payload})


def main():
    os.chdir(Path(__file__).resolve().parent)
    server = ThreadingHTTPServer(("0.0.0.0", 9000), KioskHandler)
    print("Kiosk server running on http://localhost:9000")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping kiosk server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
