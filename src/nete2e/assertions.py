import json
from collections.abc import Mapping, Sequence

from nete2e.models import Category, ProbeResult


def _require(
    ok: bool,
    expectation: str,
    result: ProbeResult,
    environment: str,
    evidence: Mapping[str, object] | None = None,
) -> None:
    if not ok:
        context = (
            f"\nEvidence: {json.dumps(dict(evidence), default=str, sort_keys=True)}"
            if evidence
            else ""
        )
        raise AssertionError(
            f"{expectation}\nSource environment: {environment}\n"
            f"{result.protocol} {result.destination}: {result.category.value} "
            f"after {result.elapsed:.3f}s\n"
            f"Details: {json.dumps(result.details, default=str, sort_keys=True)}{context}"
        )


def assert_tcp_reachable(
    result: ProbeResult, *, environment: str, evidence: Mapping[str, object] | None = None
) -> None:
    _require(
        result.category == Category.SUCCESS,
        "Expected TCP connection to succeed within its timeout.",
        result,
        environment,
        evidence,
    )


def assert_tcp_blocked(
    result: ProbeResult, *, environment: str, evidence: Mapping[str, object] | None = None
) -> None:
    _require(
        result.category == Category.TIMEOUT,
        "Expected TCP DROP policy to produce a timeout.",
        result,
        environment,
        evidence,
    )


def assert_dns_record(result: ProbeResult, addresses: Sequence[str], *, environment: str) -> None:
    _require(
        result.category == Category.SUCCESS
        and set(result.details.get("answers", [])) == set(addresses),
        f"Expected DNS A records exactly {list(addresses)}.",
        result,
        environment,
    )


def assert_dns_nxdomain(result: ProbeResult, *, environment: str) -> None:
    _require(result.category == Category.NXDOMAIN, "Expected DNS NXDOMAIN.", result, environment)


def assert_route_via(
    result: ProbeResult, gateway: str, *, environment: str, interface: str | None = None
) -> None:
    _require(
        result.category == Category.SUCCESS
        and result.details.get("gateway") == gateway
        and (interface is None or result.details.get("interface") == interface),
        f"Expected route via {gateway}" + (f" dev {interface}." if interface else "."),
        result,
        environment,
    )


def assert_http_healthy(
    result: ProbeResult, *, environment: str, evidence: Mapping[str, object] | None = None
) -> None:
    try:
        healthy = json.loads(result.details.get("body", "")) == {"status": "ok"}
    except (ValueError, TypeError):
        healthy = False
    _require(
        result.category == Category.SUCCESS
        and result.details.get("status") == 200
        and healthy
        and not result.details.get("truncated", False),
        'Expected HTTP 200 and JSON {"status":"ok"}.',
        result,
        environment,
        evidence,
    )
