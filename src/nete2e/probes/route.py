import json
import subprocess
import time
from ipaddress import IPv4Address

from nete2e.models import Category, ProbeResult, validate_endpoint


def parse_route(output: str) -> dict[str, str | None]:
    try:
        routes = json.loads(output)
        if not isinstance(routes, list) or len(routes) != 1 or not isinstance(routes[0], dict):
            raise ValueError("expected one route object")
        route = routes[0]
        destination = str(IPv4Address(route["dst"]))
        interface = route["dev"]
        if not isinstance(interface, str) or not interface:
            raise ValueError("missing route interface")
        gateway = str(IPv4Address(route["gateway"])) if "gateway" in route else None
        source = str(IPv4Address(route["prefsrc"])) if "prefsrc" in route else None
        return {
            "destination": destination,
            "gateway": gateway,
            "interface": interface,
            "source": source,
        }
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Malformed ip route JSON: {str(exc)[:256]}") from exc


def probe_route(address: str, timeout: float) -> ProbeResult:
    validate_endpoint(address, timeout)
    started = time.monotonic()
    category = Category.SUCCESS
    details: dict[str, object] = {}
    try:
        # The sole variable argument has been validated as an IPv4 literal.
        result = subprocess.run(  # noqa: S603
            ["ip", "-j", "-4", "route", "get", address],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode:
            category = Category.ERROR
            details = {"returncode": result.returncode, "error": result.stderr[:1024]}
        else:
            details = dict(parse_route(result.stdout))
    except FileNotFoundError:
        category = Category.UNSUPPORTED
        details["error"] = "Linux iproute2 tooling is unavailable"
    except subprocess.TimeoutExpired:
        category = Category.TIMEOUT
    except (OSError, ValueError) as exc:
        category = Category.ERROR
        details["error"] = str(exc)[:512]
    return ProbeResult("route", address, category, time.monotonic() - started, details)
