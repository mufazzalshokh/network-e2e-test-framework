import pytest

from nete2e.assertions import assert_tcp_reachable
from nete2e.probes.tcp import probe_tcp

pytestmark = pytest.mark.e2e


def test_allowed_tcp(config, route_evidence):
    result = probe_tcp(
        str(config.service.address),
        config.service.allowed_tcp_port,
        config.timeouts.connect_seconds,
    )
    assert_tcp_reachable(result, environment=config.environment, evidence=route_evidence)
