import socket
import time

from nete2e.models import Category, ProbeResult, socket_category, validate_endpoint


def probe_tcp(address: str, port: int, timeout: float) -> ProbeResult:
    validate_endpoint(address, timeout, port)
    started = time.monotonic()
    category = Category.SUCCESS
    details: dict[str, object] = {"address": address, "timeout_seconds": timeout}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect((address, port))
    except OSError as exc:
        category = socket_category(exc)
        details["error"] = str(exc)[:512]
    return ProbeResult("tcp", f"{address}:{port}", category, time.monotonic() - started, details)
