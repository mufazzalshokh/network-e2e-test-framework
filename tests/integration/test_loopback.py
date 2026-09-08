import socket
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import dns.message
import dns.rcode
import dns.rrset
import pytest

from nete2e.models import Category
from nete2e.probes.dns import probe_dns
from nete2e.probes.http import probe_http
from nete2e.probes.tcp import probe_tcp


def test_real_tcp_connect_and_refusal():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        assert probe_tcp("127.0.0.1", port, 1).category == Category.SUCCESS
    # Windows may retransmit once before reporting refusal on a closed local port.
    assert probe_tcp("127.0.0.1", port, 3).category == Category.REFUSED


@contextmanager
def http_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.connection.settimeout(1)
            if self.path == "/stall":
                self.server.release.wait(2)
                return
            body = b'{"status":"ok"}' if self.path == "/health" else b"x" * 8192
            self.send_response(200 if self.headers.get("Host") == "service.internal.test" else 400)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.release = threading.Event()
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02})
    thread.start()
    try:
        yield server.server_port
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_real_http_host_contract_and_body_limit():
    with http_server() as port:
        result = probe_http("127.0.0.1", port, "service.internal.test", 2)
        assert result.category == Category.SUCCESS
        assert result.details["status"] == 200
        assert result.details["body"] == '{"status":"ok"}'
        large = probe_http("127.0.0.1", port, "service.internal.test", 2, path="/large")
        assert len(large.details["body"]) <= 1024
        assert large.details["truncated"] is True


def test_real_http_deadline():
    with http_server() as port:
        result = probe_http("127.0.0.1", port, "service.internal.test", 0.1, path="/stall")
        assert result.category == Category.TIMEOUT
        assert result.elapsed < 1


def test_plain_http_does_not_load_a_certificate_store():
    with http_server() as port:
        with patch(
            "ssl.SSLContext.load_verify_locations", side_effect=AssertionError("CA store read")
        ):
            result = probe_http("127.0.0.1", port, "service.internal.test", 2)
        assert result.category == Category.SUCCESS


@pytest.mark.parametrize("negative", [False, True])
def test_real_dns_packets(negative):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind(("127.0.0.1", 0))
        server.settimeout(2)
        errors = []

        def respond():
            try:
                packet, peer = server.recvfrom(4096)
                query = dns.message.from_wire(packet)
                response = dns.message.make_response(query)
                if negative:
                    response.set_rcode(dns.rcode.NXDOMAIN)
                else:
                    response.answer.append(
                        dns.rrset.from_text("service.internal.test.", 30, "IN", "A", "192.0.2.10")
                    )
                server.sendto(response.to_wire(), peer)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=respond)
        thread.start()
        result = probe_dns("127.0.0.1", "service.internal.test", 1, port=server.getsockname()[1])
        thread.join(timeout=3)
        assert not errors
        assert not thread.is_alive()
        assert result.category == (Category.NXDOMAIN if negative else Category.SUCCESS)
        if not negative:
            assert result.details["answers"] == ["192.0.2.10"]
