import asyncio
import time

import httpx

from nete2e.models import Category, ProbeResult, validate_endpoint


async def _request(url: str, hostname: str, timeout: float) -> dict[str, object]:
    async with httpx.AsyncClient(
        timeout=timeout, trust_env=False, follow_redirects=False
    ) as client:
        async with client.stream(
            "GET", url, headers={"Host": hostname, "Accept-Encoding": "identity"}
        ) as response:
            body = bytearray()
            async for chunk in response.aiter_raw():
                body.extend(chunk[: 1025 - len(body)])
                if len(body) > 1024:
                    break
            return {
                "status": response.status_code,
                "body": bytes(body[:1024]).decode("utf-8", errors="replace"),
                "truncated": len(body) > 1024,
            }


async def _bounded_request(url: str, hostname: str, timeout: float) -> dict[str, object]:
    return await asyncio.wait_for(_request(url, hostname, timeout), timeout=timeout)


def probe_http(
    address: str, port: int, hostname: str, timeout: float, *, path: str = "/health"
) -> ProbeResult:
    validate_endpoint(address, timeout, port)
    if not path.startswith("/") or any(ord(char) < 32 for char in path + hostname):
        raise ValueError(
            "HTTP path must start with /; path and Host must not contain control characters"
        )
    url = f"http://{address}:{port}{path}"
    started = time.monotonic()
    category = Category.SUCCESS
    details: dict[str, object] = {"host": hostname, "timeout_seconds": timeout}
    try:
        details.update(asyncio.run(_bounded_request(url, hostname, timeout)))
    except (TimeoutError, httpx.TimeoutException):
        category = Category.TIMEOUT
    except (httpx.HTTPError, OSError) as exc:
        category = Category.ERROR
        details["error"] = str(exc)[:512]
    return ProbeResult("http", url, category, time.monotonic() - started, details)
