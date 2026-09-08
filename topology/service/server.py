import signal
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(2)

    def do_GET(self):
        healthy = self.path == "/health" and self.headers.get("Host") == "service.internal.test"
        body = b'{"status":"ok"}' if healthy else b'{"status":"not_found"}'
        self.send_response(200 if healthy else 404)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class EchoHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(2)
        try:
            data = self.request.recv(1024)
            if data:
                self.request.sendall(data)
        except (TimeoutError, ConnectionError):
            return


class TCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    servers = [
        ThreadingHTTPServer(("0.0.0.0", 8080), HealthHandler),
        TCPServer(("0.0.0.0", 9000), EchoHandler),
        TCPServer(("0.0.0.0", 9090), EchoHandler),
    ]
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    threads = [
        threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.1})
        for server in servers
    ]
    for thread in threads:
        thread.start()
    print("Listening on HTTP 8080 and TCP 9000/9090", flush=True)
    stop.wait()
    for server in servers:
        server.shutdown()
        server.server_close()
    for thread in threads:
        thread.join(timeout=3)


if __name__ == "__main__":
    main()
