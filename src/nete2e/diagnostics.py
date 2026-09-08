import hashlib
import json
import re
import socket
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nete2e.config import Environment
from nete2e.probes.dns import probe_dns
from nete2e.probes.route import probe_route
from nete2e.probes.tcp import probe_tcp


def _best_effort(operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except Exception as exc:
        return {"unavailable": f"{type(exc).__name__}: {str(exc)[:512]}"}


def _command(arguments: list[str]) -> dict[str, object]:
    # All callers supply fixed diagnostic argument vectors, never scenario content.
    completed = subprocess.run(  # noqa: S603
        arguments, timeout=2, capture_output=True, text=True, check=False
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout[:16384],
        "stderr": completed.stderr[:2048],
    }


def collect_diagnostics(config: Environment) -> dict[str, Any]:
    address = str(config.service.address)
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": config.environment,
        "hostname": socket.gethostname(),
        "destination": address,
        "resolv_conf": _best_effort(lambda: Path("/etc/resolv.conf").read_text()[:8192]),
        "addresses": _best_effort(lambda: _command(["ip", "-j", "addr"])),
        "routes": _best_effort(lambda: _command(["ip", "-j", "-4", "route"])),
        "route": _best_effort(
            lambda: probe_route(address, min(2, config.timeouts.route_seconds)).to_dict()
        ),
        "dns": _best_effort(
            lambda: probe_dns(
                str(config.dns.server),
                config.dns.name,
                min(2, config.timeouts.dns_seconds),
                port=config.dns.port,
            ).to_dict()
        ),
        "tcp": _best_effort(
            lambda: probe_tcp(
                address, config.service.allowed_tcp_port, min(2, config.timeouts.connect_seconds)
            ).to_dict()
        ),
    }


def write_diagnostics(directory: Path, identity: str, evidence: dict[str, Any]) -> Path:
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", identity)[:100].lstrip(".") or "failure"
    digest = hashlib.sha256(identity.encode()).hexdigest()[:12]
    path = directory / f"{name}-{digest}.json"
    path.write_text(json.dumps(evidence, indent=2, default=str) + "\n", encoding="utf-8")
    return path
