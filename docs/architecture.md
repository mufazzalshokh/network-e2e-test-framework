# Architecture

## Purpose and boundaries

The framework validates observable DNS, TCP, HTTP, route selection and forwarding
policy in a controlled network. Python probes know endpoints and deadlines, not
containers. Host orchestration owns image builds, topology lifecycle and router
evidence. Scenario files select only predefined lab failures; they cannot execute
commands. Remote environments need the same network contracts, not Docker APIs.

## Lab specification

The runner and CoreDNS occupy client-net (10.10.0.0/24). The target occupies
service-net (10.20.0.0/24). Only the router joins both networks, with addresses
10.10.0.254 and 10.20.0.254. Both Docker bridges are internal. The runner has an
explicit route to the service subnet; the target has a return route to client-net.
No application-traffic NAT, published ports, host networking or shared network
namespaces are used. Docker's embedded resolver may install its own namespace-local
DNS translation rules; application traffic does not use that resolver.

CoreDNS at 10.10.0.53 serves an authoritative internal.test zone. The target at
10.20.0.10 listens on HTTP 8080 and TCP 9000 and 9090. The router forwards 8080
and 9000 and drops 9090. Target readiness checks all three listeners locally;
the router-side control check also connects to 9090 on the service network.
This distinguishes an intentional drop from an absent listener. Runner route
selection plus real successful connections establish a routed path; firewall
counters provide corroborating evidence, not a substitute for data-plane tests.

The router needs NET_ADMIN for forwarding policy; runner and target need it only
to install routes at startup. Application processes drop capabilities before
running. No container receives privileged mode or a Docker socket.

## Configuration and probe contracts

Validated YAML specifies environment identity, IPv4 endpoints, expected DNS
answers, service ports, target subnet, next hop, optional interface and bounded
timeouts. Unknown keys are rejected. IPv4 is an explicit initial scope.
TCP and HTTP use literal addresses to avoid unbounded system resolver calls.
HTTP sends the configured hostname as Host; DNS is tested separately against the
configured server. This does not test libc resolver integration, TLS or HTTPS.

Probe results carry protocol, destination, normalized category, duration and
bounded details. Thin assertions express the expectation and include actual
evidence. Linux route inspection executes a fixed argument vector with a timeout;
missing tooling is unsupported and fails required route assertions.

Only startup readiness may poll. Each attempt receives the remaining deadline.
Policy tests are single observations with positive controls. Failure diagnostics
are best effort, bounded, and must not replace the original assertion failure.
They contain only lab evidence; external deployments should review artifact
access because internal addressing and resolver configuration are sensitive.

## Isolation and extension

Each orchestration invocation uses a unique Compose project and removes its own
containers and networks in a finally block. Deliberate DNS and firewall failures
use Compose overrides and fresh topology instances. Fixed lab subnets mean runs
on one Docker daemon must be serialized; project names alone do not prevent IPAM
overlap. Address changes require coherent edits to Compose, routes, DNS and YAML.
New tests compose probes and assertions; new providers supply environment YAML
and their own lifecycle outside the core package.
