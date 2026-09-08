import pytest

from nete2e.assertions import assert_http_healthy
from nete2e.probes.http import probe_http

pytestmark = pytest.mark.e2e


def test_http_health(config, route_evidence):
    result = probe_http(
        str(config.service.address),
        config.service.http_port,
        config.service.hostname,
        config.timeouts.http_seconds,
    )
    assert_http_healthy(result, environment=config.environment, evidence=route_evidence)
