"""single_instance.existing_is_responsive — the liveness tie-breaker.

It decides whether a held single-instance lock belongs to a LIVE app (defer
to it and exit) or a hung/dead zombie (take over and launch — the fix for the
"AERIS won't open" trap where a windowless lingering process blocked every new
launch forever).
"""

from __future__ import annotations

import http.server
import socket
import threading

from core.single_instance import existing_is_responsive


def _serve(status: int):
    """Spin a throwaway loopback health server on an ephemeral port."""
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *a):  # silence test noise
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def test_responsive_when_health_returns_200():
    srv, port = _serve(200)
    try:
        assert existing_is_responsive(timeout=1.0, port=port) is True
    finally:
        srv.shutdown()


def test_not_responsive_on_5xx():
    # Server answers but is erroring — not a healthy instance to defer to.
    srv, port = _serve(500)
    try:
        assert existing_is_responsive(timeout=1.0, port=port) is False
    finally:
        srv.shutdown()


def test_not_responsive_when_nothing_listening():
    # Grab a free port, close it, then probe it → connection refused → False.
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    free = s.getsockname()[1]
    s.close()
    assert existing_is_responsive(timeout=0.5, port=free) is False


def test_not_responsive_when_holder_hangs():
    # A socket that LISTENS but never responds = a frozen zombie holding the
    # lock. The probe must time out → unresponsive → the caller takes over.
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        assert existing_is_responsive(timeout=0.5, port=port) is False
    finally:
        s.close()
