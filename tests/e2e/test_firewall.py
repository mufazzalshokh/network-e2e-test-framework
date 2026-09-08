import pytest

from nete2e.assertions import assert_http_healthy, assert_tcp_blocked
from nete2e.probes.http import probe_http
from nete2e.probes.tcp import probe_tcp

pytestmark = pytest.mark.e2e


def test_drop_with_positive_control(config, route_evidence):
    address = str(config.service.address)
    control = probe_http(
        address, config.service.http_port, config.service.hostname, config.timeouts.http_seconds
    )
    assert_http_healthy(control, environment=config.environment, evidence=route_evidence)
    result = probe_tcp(address, config.service.blocked_tcp_port, config.timeouts.connect_seconds)
    assert_tcp_blocked(result, environment=config.environment, evidence=route_evidence)
