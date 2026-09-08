FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 iptables util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /lab

FROM runtime AS router
COPY topology/router/ /lab/
ENTRYPOINT ["/bin/sh", "/lab/entrypoint.sh"]

FROM runtime AS target
COPY topology/service/ /lab/
ENTRYPOINT ["/bin/sh", "/lab/entrypoint.sh"]

FROM runtime AS runner
COPY pyproject.toml requirements-dev.lock /lab/
COPY src/ /lab/src/
RUN python -m pip install --no-cache-dir -c requirements-dev.lock '.[dev]'
COPY tests/e2e/ /lab/tests/e2e/
COPY environments/ /lab/environments/
COPY topology/runner/entrypoint.sh /lab/entrypoint.sh
ENTRYPOINT ["/bin/sh", "/lab/entrypoint.sh"]
CMD ["python", "-m", "pytest", "tests/e2e", "-q", "--junitxml=/artifacts/junit.xml"]
