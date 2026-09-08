import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "run_e2e.py"
spec = importlib.util.spec_from_file_location("run_e2e", SCRIPT)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def report(tmp_path, cases):
    path = tmp_path / "junit.xml"
    path.write_text(f"<testsuites><testsuite>{cases}</testsuite></testsuites>", encoding="utf-8")
    return path


def test_scenario_requires_specific_failure_and_passing_controls(tmp_path):
    cases = (
        '<testcase name="test_allowed_tcp"><failure>'
        "tcp 10.20.0.10:9000: timeout</failure></testcase>"
    )
    cases += "".join(
        f'<testcase name="{name}" />' for name in module.EXPECTED_TESTS - {"test_allowed_tcp"}
    )
    module.verify_regression(report(tmp_path, cases), "firewall", 1)


@pytest.mark.parametrize(
    "body,code",
    [
        ('<testcase name="test_allowed_tcp"><error>setup failed</error></testcase>', 1),
        ('<testcase name="test_allowed_tcp"><failure>refused</failure></testcase>', 1),
        ('<testcase name="test_expected_record"><failure>DNS</failure></testcase>', 1),
        ('<testcase name="test_allowed_tcp"/>', 0),
    ],
)
def test_unrelated_failure_does_not_validate_scenario(tmp_path, body, code):
    with pytest.raises(RuntimeError):
        module.verify_regression(report(tmp_path, body), "firewall", code)


def test_baseline_requires_complete_passing_report(tmp_path):
    with pytest.raises(RuntimeError):
        module.verify_baseline(report(tmp_path, '<testcase name="test_allowed_tcp"/>'))


def test_cleanup_runs_after_startup_failure(tmp_path):
    with patch.object(module, "Lab") as factory:
        lab = factory.return_value
        lab.project = "test-lab"
        lab.command.side_effect = [RuntimeError("startup failed"), 0]
        with pytest.raises(RuntimeError, match="startup failed"):
            module.run_lab(tmp_path)
        assert lab.command.call_args.args[0][0] == "down"
        lab.diagnostics.assert_called_once()
