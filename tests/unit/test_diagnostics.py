import json
from unittest.mock import patch

from nete2e.diagnostics import collect_diagnostics, write_diagnostics
from nete2e.models import Category, ProbeResult


def test_collection_survives_unavailable_tools():
    from test_config import config_data

    from nete2e.config import Environment

    config = Environment.model_validate(config_data())
    unavailable = ProbeResult("route", "x", Category.UNSUPPORTED, 0)
    with (
        patch("nete2e.diagnostics.subprocess.run", side_effect=FileNotFoundError()),
        patch("nete2e.diagnostics.probe_route", return_value=unavailable),
        patch("nete2e.diagnostics.probe_dns", side_effect=RuntimeError("broken probe")),
        patch("nete2e.diagnostics.probe_tcp", return_value=unavailable),
    ):
        evidence = collect_diagnostics(config)
    assert evidence["environment"] == "lab"
    assert evidence["hostname"]
    assert "broken probe" in str(evidence["dns"])
    assert "unsupported" in str(evidence["route"])
    assert "unavailable" in str(evidence["addresses"])


def test_artifacts_are_json_and_cannot_escape_directory(tmp_path):
    path = write_diagnostics(tmp_path, "../../bad::test[1]", {"result": "timeout"})
    assert path.parent == tmp_path.resolve()
    assert json.loads(path.read_text()) == {"result": "timeout"}
