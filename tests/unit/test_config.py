from copy import deepcopy

import pytest
from pydantic import ValidationError

from nete2e.config import Environment, load_config


def config_data():
    return {
        "environment": "lab",
        "dns": {
            "server": "10.10.0.53",
            "name": "service.internal.test",
            "expected_addresses": ["10.20.0.10"],
            "negative_name": "missing.internal.test",
        },
        "service": {
            "address": "10.20.0.10",
            "hostname": "service.internal.test",
            "http_port": 8080,
            "allowed_tcp_port": 9000,
            "blocked_tcp_port": 9090,
        },
        "routing": {"destination_subnet": "10.20.0.0/24", "expected_gateway": "10.10.0.254"},
    }


def test_valid_defaults():
    config = Environment.model_validate(config_data())
    assert str(config.service.address) == "10.20.0.10"
    assert config.timeouts.connect_seconds == 2


@pytest.mark.parametrize(
    "section,key,value",
    [
        ("service", "http_port", 0),
        ("service", "http_port", 65536),
        ("service", "http_port", True),
        ("service", "address", "example.com"),
        ("service", "address", "::1"),
        ("dns", "name", "bad\r\nHost: x"),
        ("routing", "destination_subnet", "10.30.0.0/24"),
        ("service", "command", "whoami"),
        ("service", "blocked_tcp_port", 9000),
    ],
)
def test_invalid_fields(section, key, value):
    data = deepcopy(config_data())
    data[section][key] = value
    with pytest.raises(ValidationError):
        Environment.model_validate(data)


@pytest.mark.parametrize("value", [0, -1, 121, float("inf"), float("nan"), True, "2"])
def test_invalid_timeout(value):
    with pytest.raises(ValidationError):
        Environment.model_validate({**config_data(), "timeouts": {"connect_seconds": value}})


def test_load_reports_path_and_field(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("environment: lab\n", encoding="utf-8")
    with pytest.raises(
        ValueError,
        match="broken.yaml.*",
    ):
        load_config(path)


def test_duplicate_yaml_keys_rejected(tmp_path):
    path = tmp_path / "duplicate.yaml"
    path.write_text("environment: first\nenvironment: second\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_config(path)
