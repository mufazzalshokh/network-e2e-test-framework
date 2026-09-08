import json
import os
from pathlib import Path

import pytest

from nete2e.config import load_config
from nete2e.diagnostics import collect_diagnostics, write_diagnostics
from nete2e.probes.route import probe_route


@pytest.fixture(scope="session")
def config():
    return load_config(os.environ.get("NETE2E_CONFIG", "environments/docker.yaml"))


@pytest.fixture
def route_evidence(config):
    return probe_route(str(config.service.address), config.timeouts.route_seconds).to_dict()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if not report.failed:
        return
    try:
        config = item.funcargs.get("config") or load_config(
            os.environ.get("NETE2E_CONFIG", "environments/docker.yaml")
        )
        evidence = collect_diagnostics(config)
        artifact = write_diagnostics(
            Path(os.environ.get("NETE2E_ARTIFACTS", "artifacts/runner")), item.nodeid, evidence
        )
        report.sections.append(("network evidence", json.dumps(evidence, indent=2)))
        report.sections.append(("diagnostic artifact", str(artifact)))
    except Exception as exc:
        report.sections.append(("diagnostics unavailable", f"{type(exc).__name__}: {exc}"))
