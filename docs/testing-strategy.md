# Testing strategy

## Acceptance specification

* DNS: an explicit query to the configured resolver returns exactly the expected
  A records for service.internal.test. missing.internal.test returns NXDOMAIN.
  Timeout, SERVFAIL and empty answers remain separate outcomes.
* TCP: port 9000 connects within its deadline. A live port 9090 cannot be reached
  from the client and must time out under the DROP policy. Name errors, refused
  connections and unreachable networks are not accepted as evidence of a drop.
* HTTP: GET /health to the configured address, with the configured Host header,
  returns status 200 and the bounded JSON body {"status":"ok"} through the router.
* Routing: ip -j -4 route get reports the intended gateway and, when configured,
  interface. The target is inside the configured destination subnet. Successful
  HTTP/TCP requests supplement this control-plane observation.
* Firewall: positive controls pass before testing denial. The target's blocked
  listener is verified from the router's service side by host orchestration.
* Diagnostics: failure evidence identifies environment, source, destination,
  protocol, duration and category, with DNS and route evidence where available.
  Collection failures are recorded without masking the test failure.

## Layers and development

Core behavior is developed with failing unit tests first: validation, error
normalization, route parsing, assertion formatting, deadline accounting and
diagnostic fallbacks. Network errors are injected at unit boundaries. Separate
loopback integration tests use real sockets for portable protocol checks; they
do not prove Docker routing or firewall behavior.

Container E2E tests use real DNS packets, TCP connections, HTTP requests and
Linux route lookup. They are explicitly selected and never silently skipped
when requested. Default pytest runs only unit and loopback tests.

Startup polls positive DNS/TCP/HTTP readiness within an overall deadline. A
firewall assertion never polls until it happens to pass. Test observations do
not mutate policy. Host scripts bound Compose operations, capture JUnit and
failure evidence, and always attempt teardown, including on interruption.

## Regression scenarios

The firewall override drops the normally allowed TCP port 9000. The DNS override
serves the wrong address for the known name. Each scenario starts fresh, verifies
the base readiness contract, then recreates only the affected component. The
normal suite must fail in the matching test with a specific category. A failing
process alone is insufficient: the scenario harness inspects JUnit identities
and failure text and rejects setup errors or unrelated failures. Teardown restores
isolation. Baseline E2E runs twice from clean topology in integration CI.

## Evidence and limits

Ruff, strict mypy, unit tests, package installation and configuration validation
run locally and in Python 3.11/3.12 CI. Integration CI builds the lab, validates
Compose, runs baseline twice and exercises both regressions. JUnit is always
retained; detailed network evidence is collected only on failure.

Hosted workflow execution, actual container execution and static YAML checks
are distinct validation levels. Documentation must report these separately.
IPsec is outside the base scope and may be added only after base E2E is verified;
it would require real IKE/ESP associations, XFRM policy and protected traffic
evidence on a kernel-capable isolated lab. No encryption claim follows from
ordinary TCP connectivity.
