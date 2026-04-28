from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os


class KioskHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()


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
