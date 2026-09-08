"""Static contract checks; does not claim hosted CI or container execution."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    # BaseLoader preserves GitHub's 'on' key instead of YAML 1.1 boolean coercion.
    # BaseLoader constructs only strings, lists and mappings.
    return yaml.load(
        (ROOT / path).read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,  # noqa: S506
    )


def main():
    compose = read("docker-compose.yml")
    services = compose["services"]
    require(set(services["e2e-runner"]["networks"]) == {"client-net"}, "runner bypasses router")
    require(
        set(services["target-service"]["networks"]) == {"service-net"}, "target bypasses router"
    )
    require(set(services["router"]["networks"]) == {"client-net", "service-net"}, "router topology")
    for service in services.values():
        require("privileged" not in service and "network_mode" not in service, "unsafe namespace")
        require("ports" not in service, "unexpected host port")
        require("docker.sock" not in str(service), "Docker socket mounted")
    workflow = read(".github/workflows/ci.yml")
    require(set(workflow["jobs"]) == {"quality", "unit", "e2e"}, "GitHub jobs missing")
    require(set(workflow["on"]) == {"push", "pull_request", "workflow_dispatch"}, "GitHub triggers")
    require(
        workflow["jobs"]["unit"]["strategy"]["matrix"]["python"] == ["3.11", "3.12"],
        "GitHub Python matrix",
    )
    gitlab = read(".gitlab-ci.yml")
    require(gitlab["stages"] == ["quality", "unit", "build", "e2e"], "GitLab stages")
    require(gitlab["e2e"]["artifacts"]["when"] == "always", "GitLab failure artifacts")
    print("Compose isolation and CI structural contracts passed (not hosted execution).")


if __name__ == "__main__":
    main()
