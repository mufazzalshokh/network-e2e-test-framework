import math
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class ReadinessTimeout(TimeoutError):
    def __init__(self, timeout: float, last: object) -> None:
        self.last = last
        super().__init__(f"Readiness deadline {timeout:.3f}s expired; last evidence: {last}")


def poll(
    attempt: Callable[[float], T],
    ready: Callable[[T], bool],
    *,
    timeout: float,
    interval: float = 0.2,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """The attempt must honor its supplied remaining time budget."""
    if not all(math.isfinite(value) and value > 0 for value in (timeout, interval)):
        raise ValueError("timeout and interval must be positive and finite")
    deadline = clock() + timeout
    last: T | None = None
    while (remaining := deadline - clock()) > 0:
        last = attempt(remaining)
        if clock() <= deadline and ready(last):
            return last
        remaining = deadline - clock()
        if remaining > 0:
            sleep(min(interval, remaining))
    raise ReadinessTimeout(timeout, last)
