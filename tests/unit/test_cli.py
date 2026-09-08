import json
from unittest.mock import patch

from nete2e.cli import main
from nete2e.models import Category, ProbeResult


def test_cli_config_and_probe(capsys):
    assert main(["--config", "environments/docker.yaml", "check-config"]) == 0
    assert "docker/client" in capsys.readouterr().out
    with patch(
        "nete2e.cli.probe_tcp", return_value=ProbeResult("tcp", "target", Category.REFUSED, 0)
    ):
        assert main(["--config", "environments/docker.yaml", "probe", "tcp"]) == 1
    assert json.loads(capsys.readouterr().out)["category"] == "refused"


def test_cli_bad_config(capsys):
    assert main(["--config", "missing.yaml", "check-config"]) == 2
    assert "missing.yaml" in capsys.readouterr().err
