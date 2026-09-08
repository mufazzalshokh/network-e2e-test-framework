"""Host-side Compose lifecycle; no Docker access inside the runner."""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TESTS = {
    "test_expected_record",
    "test_unknown_name",
    "test_allowed_tcp",
    "test_http_health",
    "test_expected_gateway",
    "test_drop_with_positive_control",
}


def verify_baseline(path: Path) -> int:
    if path.stat().st_size > 2_000_000:
        raise RuntimeError("Unexpectedly large JUnit report")
    cases = ET.parse(path).findall(".//testcase")  # noqa: S314 - local pytest artifact
    names = [case.attrib["name"] for case in cases]
    if len(names) != len(EXPECTED_TESTS) or set(names) != EXPECTED_TESTS:
        raise RuntimeError(f"Incomplete baseline test report: {names}")
    if any(
        len(case.findall("failure") + case.findall("error") + case.findall("skipped"))
        for case in cases
    ):
        raise RuntimeError("Baseline contains failed, errored or skipped tests")
    return len(cases)


def verify_regression(path: Path, scenario: str, returncode: int) -> None:
    if returncode != 1:
        raise RuntimeError(f"Expected pytest assertion failure (exit 1), got {returncode}")
    if path.stat().st_size > 2_000_000:
        raise RuntimeError("Unexpectedly large JUnit report")
    cases = ET.parse(path).findall(".//testcase")  # noqa: S314 - local pytest-generated artifact
    names = [case.attrib["name"] for case in cases]
    if len(names) != len(EXPECTED_TESTS) or set(names) != EXPECTED_TESTS:
        raise RuntimeError(f"Incomplete scenario test report: {names}")
    if any(case.find("error") is not None or case.find("skipped") is not None for case in cases):
        raise RuntimeError("Scenario had setup errors or skipped tests")
    failures = {
        case.attrib["name"]: case.find("failure")
        for case in cases
        if case.find("failure") is not None
    }
    expected = "test_allowed_tcp" if scenario == "firewall" else "test_expected_record"
    if set(failures) != {expected}:
        raise RuntimeError(f"Expected only {expected} to fail, got {list(failures)}")
    failure_text = "".join(failures[expected].itertext())
    tokens = ["10.20.0.10:9000", "timeout"] if scenario == "firewall" else ["DNS", "10.20.0.99"]
    if not all(token in failure_text for token in tokens):
        raise RuntimeError(f"Failure did not identify the intended {scenario} regression")


class Lab:
    def __init__(self, artifact_dir: Path):
        self.artifact_dir = artifact_dir.resolve()
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        # The unprivileged container writer needs access to this ephemeral output directory.
        if os.name != "nt":
            self.artifact_dir.chmod(0o777)  # noqa: S103
        self.project = f"nete2e-{uuid.uuid4().hex[:12]}"
        docker = shutil.which("docker")
        if docker is None:
            raise RuntimeError("Docker CLI is unavailable")
        self.base = [
            docker,
            "compose",
            "--project-name",
            self.project,
            "--file",
            str(ROOT / "docker-compose.yml"),
        ]
        self.environment = {**os.environ, "NETE2E_ARTIFACT_DIR": str(self.artifact_dir)}
        (self.artifact_dir / "project.json").write_text(
            json.dumps({"project": self.project}) + "\n", encoding="utf-8"
        )

    def command(self, args, *, timeout=120, log="compose.log", check=True, scenario=None):
        command = list(self.base)
        if scenario:
            command += ["--file", str(ROOT / "topology" / "scenarios" / f"{scenario}.yml")]
        command += args
        with (self.artifact_dir / log).open("a", encoding="utf-8") as output:
            result = subprocess.run(  # noqa: S603 - arguments come only from this orchestrator
                command,
                cwd=ROOT,
                env=self.environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                check=False,
            )
        if check and result.returncode:
            raise RuntimeError(
                f"Compose {' '.join(args[:3])} exited {result.returncode}; see {log}"
            )
        return result.returncode

    def diagnostics(self):
        commands = {
            "compose-ps.json": ["ps", "--all", "--format", "json"],
            "services.log": [
                "logs",
                "--no-color",
                "--tail",
                "150",
                "router",
                "dns",
                "target-service",
            ],
            "router-routes.json": ["exec", "-T", "router", "ip", "-j", "route"],
            "firewall.txt": ["exec", "-T", "router", "iptables-save", "-c"],
            "target-listeners.txt": ["exec", "-T", "target-service", "ss", "-lnt"],
        }
        for name, args in commands.items():
            try:
                self.command(args, timeout=15, log=name, check=False)
            except (OSError, subprocess.TimeoutExpired) as exc:
                (self.artifact_dir / name).write_text(f"Unavailable: {exc}\n", encoding="utf-8")


def run_lab(artifact_dir: Path, *, scenario=None, build=False):
    lab = Lab(artifact_dir)
    print(f"Starting {scenario or 'baseline'}: {lab.project}", flush=True)
    failure = None
    try:
        lab.command(["config", "--quiet"])
        if build:
            lab.command(["build"], timeout=900, log="build.log")
        lab.command(
            ["up", "--detach", "--wait", "--wait-timeout", "45", "router", "dns", "target-service"],
            timeout=90,
        )
        lab.command(["run", "--rm", "--no-deps", "e2e-runner", "nete2e", "ready"], timeout=60)
        # A direct service-side connection proves that port 9090 really is listening.
        lab.command(
            [
                "exec",
                "-T",
                "router",
                "python",
                "-c",
                "import socket; "
                "s=socket.create_connection(('10.20.0.10',9090),timeout=2); s.close()",
            ]
        )
        if scenario:
            service = "router" if scenario == "firewall" else "dns"
            lab.command(
                [
                    "up",
                    "--detach",
                    "--no-deps",
                    "--force-recreate",
                    "--wait",
                    "--wait-timeout",
                    "30",
                    service,
                ],
                scenario=scenario,
                timeout=60,
            )
            if scenario == "dns":
                # Query the still-existing negative name until the replacement DNS server answers.
                lab.command(
                    [
                        "run",
                        "--rm",
                        "--no-deps",
                        "e2e-runner",
                        "python",
                        "-c",
                        "from nete2e.probes.dns import probe_dns; "
                        "from nete2e.retry import poll; "
                        "from nete2e.models import Category; "
                        "poll(lambda t: probe_dns('10.10.0.53','missing.internal.test',min(t,1)), "
                        "lambda r: r.category==Category.NXDOMAIN,timeout=15)",
                    ],
                    timeout=30,
                )
        code = lab.command(
            ["run", "--rm", "--no-deps", "e2e-runner"], timeout=180, log="pytest.log", check=False
        )
        if code:
            lab.diagnostics()
        if scenario:
            verify_regression(lab.artifact_dir / "junit.xml", scenario, code)
            print(f"Detected expected {scenario} regression; all other checks passed.", flush=True)
        elif code:
            raise RuntimeError(f"Baseline pytest failed with exit {code}")
        else:
            count = verify_baseline(lab.artifact_dir / "junit.xml")
            print(f"Baseline: {count} passed.", flush=True)
    except BaseException as exc:
        failure = exc
        lab.diagnostics()
        raise
    finally:
        try:
            lab.command(
                ["down", "--volumes", "--remove-orphans", "--timeout", "5"],
                timeout=45,
                log="cleanup.log",
            )
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            if failure is None:
                raise
            print(f"Cleanup also failed for {lab.project}: {exc}", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, choices=range(1, 4), default=1)
    parser.add_argument(
        "--scenarios", action="store_true", help="also validate DNS/firewall regressions"
    )
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args(argv)
    run_id = uuid.uuid4().hex[:12]
    output = ROOT / "artifacts" / run_id
    try:
        for iteration in range(args.repeat):
            run_lab(
                output / f"baseline-{iteration + 1}", build=not args.no_build and iteration == 0
            )
        if args.scenarios:
            for scenario in ("firewall", "dns"):
                run_lab(output / scenario, scenario=scenario)
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ET.ParseError) as exc:
        print(f"E2E failed: {exc}\nArtifacts: {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":

    def interrupted(signum, frame):
        raise KeyboardInterrupt(f"Received signal {signum}")

    signal.signal(signal.SIGTERM, interrupted)
    sys.exit(main())
