import argparse
import json
import sys
import time
from collections.abc import Sequence
from functools import partial

from nete2e.assertions import assert_dns_record, assert_http_healthy, assert_tcp_reachable
from nete2e.config import Environment, load_config
from nete2e.models import Category, ProbeResult
from nete2e.probes.dns import probe_dns
from nete2e.probes.http import probe_http
from nete2e.probes.route import probe_route
from nete2e.probes.tcp import probe_tcp
from nete2e.retry import poll


def run_probe(config: Environment, protocol: str, budget: float = 120) -> ProbeResult:
    address = str(config.service.address)
    match protocol:
        case "dns":
            return probe_dns(
                str(config.dns.server),
                config.dns.name,
                min(budget, config.timeouts.dns_seconds),
                port=config.dns.port,
            )
        case "tcp":
            return probe_tcp(
                address,
                config.service.allowed_tcp_port,
                min(budget, config.timeouts.connect_seconds),
            )
        case "http":
            return probe_http(
                address,
                config.service.http_port,
                config.service.hostname,
                min(budget, config.timeouts.http_seconds),
            )
        case "route":
            return probe_route(address, min(budget, config.timeouts.route_seconds))
        case _:
            raise ValueError(f"Unknown protocol: {protocol}")


def wait_ready(config: Environment) -> None:
    deadline = time.monotonic() + config.timeouts.readiness_seconds

    def acceptable(result: ProbeResult) -> bool:
        try:
            match result.protocol:
                case "dns":
                    assert_dns_record(
                        result,
                        [str(ip) for ip in config.dns.expected_addresses],
                        environment=config.environment,
                    )
                case "tcp":
                    assert_tcp_reachable(result, environment=config.environment)
                case "http":
                    assert_http_healthy(result, environment=config.environment)
        except AssertionError:
            return False
        return True

    for protocol in ("dns", "tcp", "http"):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Readiness deadline expired before {protocol}")
        poll(partial(run_probe, config, protocol), acceptable, timeout=remaining)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe a configured IPv4 test environment")
    parser.add_argument("--config", default="environments/docker.yaml")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-config")
    commands.add_parser("ready")
    probe = commands.add_parser("probe")
    probe.add_argument("protocol", choices=("dns", "tcp", "http", "route"))
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "check-config":
            print(f"Valid configuration: {config.environment}")
            return 0
        if args.command == "ready":
            wait_ready(config)
            print(f"Ready: {config.environment}")
            return 0
        result = run_probe(config, args.protocol)
        print(json.dumps(result.to_dict(), sort_keys=True))
        return 0 if result.category == Category.SUCCESS else 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
