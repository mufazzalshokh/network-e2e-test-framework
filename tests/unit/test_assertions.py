import pytest

from nete2e.assertions import (
    assert_dns_record,
    assert_http_healthy,
    assert_route_via,
    assert_tcp_blocked,
)
from nete2e.models import Category, ProbeResult


@pytest.mark.parametrize(
    "category",
    [Category.REFUSED, Category.NAME_ERROR, Category.ERROR, Category.UNREACHABLE, Category.SUCCESS],
)
def test_drop_does_not_accept_unrelated_failures(category):
    result = ProbeResult("tcp", "10.20.0.10:9090", category, 0.2)
    with pytest.raises(AssertionError, match="10.20.0.10:9090"):
        assert_tcp_blocked(result, environment="lab/client")


def test_failure_contains_source_timing_category_and_evidence():
    result = ProbeResult("tcp", "10.20.0.10:9090", Category.REFUSED, 0.125)
    with pytest.raises(AssertionError) as error:
        assert_tcp_blocked(result, environment="lab/client", evidence={"gateway": "10.10.0.254"})
    for expected in ["lab/client", "0.125", "refused", "10.10.0.254", "tcp"]:
        assert expected in str(error.value)


def test_drop_accepts_only_timeout():
    assert_tcp_blocked(ProbeResult("tcp", "x", Category.TIMEOUT, 1), environment="lab")


def test_dns_rejects_unexpected_extra_answer():
    result = ProbeResult(
        "dns", "host", Category.SUCCESS, 0, {"answers": ["192.0.2.1", "192.0.2.2"]}
    )
    with pytest.raises(AssertionError, match="DNS"):
        assert_dns_record(result, ["192.0.2.1"], environment="lab")


def test_route_unsupported_fails_required_assertion():
    with pytest.raises(AssertionError, match="unsupported"):
        assert_route_via(
            ProbeResult("route", "x", Category.UNSUPPORTED, 0), "192.0.2.1", environment="lab"
        )


@pytest.mark.parametrize(
    "details",
    [
        {"status": 503, "body": '{"status":"ok"}'},
        {"status": 200, "body": '{"status":"down"}'},
        {"status": 200, "body": "invalid"},
    ],
)
def test_http_contract(details):
    with pytest.raises(AssertionError, match="HTTP"):
        assert_http_healthy(
            ProbeResult("http", "endpoint", Category.SUCCESS, 0, details), environment="lab"
        )
