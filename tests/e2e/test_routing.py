import pytest

from nete2e.assertions import assert_route_via
from nete2e.probes.route import probe_route

pytestmark = pytest.mark.e2e


def test_expected_gateway(config):
    result = probe_route(str(config.service.address), config.timeouts.route_seconds)
    assert_route_via(
        result,
        str(config.routing.expected_gateway),
        environment=config.environment,
        interface=config.routing.expected_interface,
    )
