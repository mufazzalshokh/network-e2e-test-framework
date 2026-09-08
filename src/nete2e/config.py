from ipaddress import IPv4Address, IPv4Network
from pathlib import Path
from typing import Annotated, Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Port = Annotated[int, Field(strict=True, ge=1, le=65535)]
Seconds = Annotated[float, Field(strict=True, gt=0, le=120, allow_inf_nan=False)]
Hostname = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=253,
        pattern=r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.?$",
    ),
]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DNSConfig(Model):
    server: IPv4Address
    port: Port = 53
    name: Hostname
    expected_addresses: Annotated[tuple[IPv4Address, ...], Field(min_length=1)]
    negative_name: Hostname


class ServiceConfig(Model):
    address: IPv4Address
    hostname: Hostname
    http_port: Port
    allowed_tcp_port: Port
    blocked_tcp_port: Port


class RoutingConfig(Model):
    destination_subnet: IPv4Network
    expected_gateway: IPv4Address
    expected_interface: (
        Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_.:-]{1,15}$")] | None
    ) = None


class Timeouts(Model):
    connect_seconds: Seconds = 2
    dns_seconds: Seconds = 2
    http_seconds: Seconds = 3
    route_seconds: Seconds = 2
    readiness_seconds: Seconds = 30


class Environment(Model):
    environment: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z0-9_./-]{1,80}$")]
    dns: DNSConfig
    service: ServiceConfig
    routing: RoutingConfig
    timeouts: Timeouts = Timeouts()

    @model_validator(mode="after")
    def coherent_endpoints(self) -> Self:
        if self.service.address not in self.routing.destination_subnet:
            raise ValueError("service.address must be within routing.destination_subnet")
        ports = (
            self.service.http_port,
            self.service.allowed_tcp_port,
            self.service.blocked_tcp_port,
        )
        if len(set(ports)) != 3:
            raise ValueError("service ports must be distinct")
        if self.service.address not in self.dns.expected_addresses:
            raise ValueError("dns.expected_addresses must include service.address")
        if self.dns.name.rstrip(".").lower() == self.dns.negative_name.rstrip(".").lower():
            raise ValueError("dns.negative_name must differ from dns.name")
        return self


class UniqueSafeLoader(yaml.SafeLoader):
    """Reject ambiguous duplicate mappings while retaining safe YAML types."""


def _unique_mapping(loader: UniqueSafeLoader, node: yaml.MappingNode) -> dict[str, Any]:
    mapping: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str):
            raise ValueError("configuration mapping keys must be strings")
        if key in mapping:
            raise ValueError(f"duplicate configuration key: {key}")
        mapping[key] = loader.construct_object(value_node, deep=True)
    return mapping


UniqueSafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_config(path: str | Path) -> Environment:
    path = Path(path)
    try:
        if path.stat().st_size > 65536:
            raise ValueError("configuration exceeds 64 KiB")
        # This loader subclasses SafeLoader and only adds duplicate-key rejection.
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueSafeLoader)  # noqa: S506
        return Environment.model_validate(data)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ValueError(f"Invalid configuration {path}: {exc}") from exc
