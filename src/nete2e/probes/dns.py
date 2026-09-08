import time

import dns.exception
import dns.resolver

from nete2e.models import Category, ProbeResult, validate_endpoint


def probe_dns(server: str, name: str, timeout: float, *, port: int = 53) -> ProbeResult:
    validate_endpoint(server, timeout, port)
    started = time.monotonic()
    details: dict[str, object] = {
        "resolver": server,
        "port": port,
        "answers": [],
        "timeout_seconds": timeout,
    }
    category = Category.SUCCESS
    resolver = dns.resolver.Resolver(configure=False)
    resolver.nameservers = [server]
    resolver.port = port
    resolver.timeout = timeout
    try:
        answer = resolver.resolve(name, "A", lifetime=timeout, search=False)
        details["answers"] = sorted({record.address for record in answer})
        details["ttl"] = answer.rrset.ttl if answer.rrset else None
        if not details["answers"]:
            category = Category.NO_ANSWER
    except dns.resolver.NXDOMAIN:
        category = Category.NXDOMAIN
    except dns.resolver.NoAnswer:
        category = Category.NO_ANSWER
    except dns.exception.Timeout:
        category = Category.TIMEOUT
    except dns.resolver.NoNameservers as exc:
        category = Category.RESOLVER_FAILURE
        details["error"] = str(exc)[:512]
    except (dns.exception.DNSException, OSError) as exc:
        category = Category.ERROR
        details["error"] = str(exc)[:512]
    return ProbeResult("dns", name, category, time.monotonic() - started, details)
