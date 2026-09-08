import pytest

from nete2e.assertions import assert_dns_nxdomain, assert_dns_record
from nete2e.probes.dns import probe_dns

pytestmark = pytest.mark.e2e


def test_expected_record(config):
    result = probe_dns(
        str(config.dns.server), config.dns.name, config.timeouts.dns_seconds, port=config.dns.port
    )
    assert_dns_record(
        result, [str(ip) for ip in config.dns.expected_addresses], environment=config.environment
    )


def test_unknown_name(config):
    result = probe_dns(
        str(config.dns.server),
        config.dns.negative_name,
        config.timeouts.dns_seconds,
        port=config.dns.port,
    )
    assert_dns_nxdomain(result, environment=config.environment)
