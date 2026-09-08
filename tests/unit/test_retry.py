import pytest

from nete2e.retry import ReadinessTimeout, poll


class Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def test_retry_passes_remaining_budget_and_preserves_evidence():
    clock = Clock()
    budgets = []

    def attempt(remaining):
        budgets.append(remaining)
        return "not yet"

    with pytest.raises(ReadinessTimeout, match="not yet") as failure:
        poll(
            attempt,
            lambda value: value == "ready",
            timeout=1,
            interval=0.4,
            clock=clock.time,
            sleep=clock.sleep,
        )
    assert budgets == pytest.approx([1, 0.6, 0.2])
    assert clock.now == pytest.approx(1)
    assert failure.value.last == "not yet"


def test_success_returns_without_sleep():
    clock = Clock()
    assert (
        poll(
            lambda remaining: "ready",
            lambda result: True,
            timeout=1,
            clock=clock.time,
            sleep=clock.sleep,
        )
        == "ready"
    )
    assert clock.now == 0


def test_late_success_is_rejected():
    clock = Clock()

    def attempt(remaining):
        clock.now += remaining + 0.01
        return True

    with pytest.raises(ReadinessTimeout):
        poll(attempt, bool, timeout=1, clock=clock.time, sleep=clock.sleep)


@pytest.mark.parametrize("timeout,interval", [(0, 1), (1, 0), (-1, 1), (float("inf"), 1)])
def test_invalid_policy(timeout, interval):
    with pytest.raises(ValueError):
        poll(lambda remaining: False, bool, timeout=timeout, interval=interval)
