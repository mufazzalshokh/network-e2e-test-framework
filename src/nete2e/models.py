import errno
import math
import socket
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from ipaddress import IPv4Address
from typing import Any


class Category(StrEnum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    REFUSED = "refused"
    NAME_ERROR = "name_error"
    UNREACHABLE = "unreachable"
    NXDOMAIN = "nxdomain"
    NO_ANSWER = "no_answer"
    RESOLVER_FAILURE = "resolver_failure"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass(frozen=True)
class ProbeResult:
    protocol: str
    destination: str
    category: Category
    elapsed: float
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_endpoint(address: str, timeout: float, port: int | None = None) -> None:
    try:
        IPv4Address(address)
    except ValueError as exc:
        raise ValueError(
            "probe address must be an IPv4 literal; use the DNS probe for names"
        ) from exc
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 120:
        raise ValueError("timeout must be finite and within (0, 120] seconds")
    if port is not None and (
        isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535
    ):
        raise ValueError("port must be an integer within [1, 65535]")


def socket_category(exc: OSError) -> Category:
    if isinstance(exc, TimeoutError):
        return Category.TIMEOUT
    if isinstance(exc, socket.gaierror):
        return Category.NAME_ERROR
    if isinstance(exc, ConnectionRefusedError) or exc.errno == errno.ECONNREFUSED:
        return Category.REFUSED
    if exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
        return Category.UNREACHABLE
    return Category.ERROR
