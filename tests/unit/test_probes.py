import errno
import json
import socket
import subprocess
from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver
import pytest

from nete2e.models import Category
from nete2e.probes.dns import probe_dns
from nete2e.probes.route import parse_route, probe_route
from nete2e.probes.tcp import probe_tcp


@pytest.mark.parametrize(
    "error,category",
    [
        (TimeoutError(), Category.TIMEOUT),
        (ConnectionRefusedError(errno.ECONNREFUSED, "refused"), Category.REFUSED),
        (OSError(errno.ENETUNREACH, "unreachable"), Category.UNREACHABLE),
        (OSError(errno.EHOSTUNREACH, "unreachable"), Category.UNREACHABLE),
        (socket.gaierror("name"), Category.NAME_ERROR),
        (OSError(errno.EACCES, "permission"), Category.ERROR),
    ],
)
def test_tcp_error_categories(error, category):
    with patch("nete2e.probes.tcp.socket.socket") as factory:
        sock = factory.return_value.__enter__.return_value
        sock.connect.side_effect = error
        result = probe_tcp("192.0.2.1", 9000, 0.2)
    assert result.category == category
    assert result.destination == "192.0.2.1:9000"
    assert result.elapsed >= 0
    sock.settimeout.assert_called_once_with(0.2)


def test_tcp_rejects_hostname_without_system_dns():
    with patch("socket.getaddrinfo") as lookup:
        with pytest.raises(ValueError, match="IPv4"):
            probe_tcp("example.test", 80, 1)
    lookup.assert_not_called()


@pytest.mark.parametrize(
    "error,category",
    [
        (dns.resolver.NXDOMAIN(), Category.NXDOMAIN),
        (dns.resolver.NoAnswer(), Category.NO_ANSWER),
        (dns.exception.Timeout(), Category.TIMEOUT),
        (dns.resolver.NoNameservers(), Category.RESOLVER_FAILURE),
    ],
)
def test_dns_categories_and_explicit_resolver(error, category):
    with patch("nete2e.probes.dns.dns.resolver.Resolver") as factory:
        resolver = factory.return_value
        resolver.resolve.side_effect = error
        result = probe_dns("192.0.2.53", "service.internal.test", 0.5)
    factory.assert_called_once_with(configure=False)
    assert resolver.nameservers == ["192.0.2.53"]
    assert result.category == category
    assert result.details["resolver"] == "192.0.2.53"
    assert resolver.resolve.call_args.kwargs["lifetime"] == 0.5
    assert resolver.resolve.call_args.kwargs["search"] is False


def test_dns_answers():
    answer = MagicMock()
    answer.__iter__.return_value = iter([MagicMock(address="192.0.2.10")])
    answer.rrset.ttl = 30
    with patch("nete2e.probes.dns.dns.resolver.Resolver") as factory:
        factory.return_value.resolve.return_value = answer
        result = probe_dns("192.0.2.53", "service.internal.test", 1)
    assert result.category == Category.SUCCESS
    assert result.details["answers"] == ["192.0.2.10"]
    assert result.details["ttl"] == 30


def test_route_parsing():
    route = parse_route(
        json.dumps(
            [{"dst": "10.20.0.10", "gateway": "10.10.0.254", "dev": "eth0", "prefsrc": "10.10.0.2"}]
        )
    )
    assert route == {
        "destination": "10.20.0.10",
        "gateway": "10.10.0.254",
        "interface": "eth0",
        "source": "10.10.0.2",
    }


@pytest.mark.parametrize(
    "output", ["bad", "[]", "{}", '[{"dst":"x"}]', '[{"dst":"10.20.0.10","dev":3}]']
)
def test_malformed_route(output):
    with pytest.raises(ValueError):
        parse_route(output)


def test_direct_route_has_no_fabricated_gateway():
    result = parse_route('[{"dst":"10.20.0.10","dev":"eth0"}]')
    assert result["gateway"] is None


@pytest.mark.parametrize(
    "error,category",
    [
        (FileNotFoundError(), Category.UNSUPPORTED),
        (subprocess.TimeoutExpired("ip", 1), Category.TIMEOUT),
    ],
)
def test_route_tool_failures(error, category):
    with patch("nete2e.probes.route.subprocess.run", side_effect=error):
        assert probe_route("192.0.2.1", 1).category == category


def test_route_command_is_bounded_and_uses_argument_array():
    with patch("nete2e.probes.route.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess(
            [], 0, '[{"dst":"192.0.2.1","dev":"eth0"}]', ""
        )
        result = probe_route("192.0.2.1", 0.5)
    assert result.category == Category.SUCCESS
    assert run.call_args.args[0] == ["ip", "-j", "-4", "route", "get", "192.0.2.1"]
    assert run.call_args.kwargs["timeout"] == 0.5
    assert not run.call_args.kwargs.get("shell", False)
