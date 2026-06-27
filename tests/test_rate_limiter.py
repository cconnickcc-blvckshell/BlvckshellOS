"""Tests for the Anthropic input-token-per-minute rate limiter.

These prove the *mechanism* deterministically with a controllable clock: that
the bucket lets calls through while budget remains, holds a call back once the
per-minute budget is spent, refills over time, and applies backpressure when a
call's real usage exceeds the up-front estimate. They do NOT (and cannot here)
prove the chosen 28k/min threshold prevents a 429 against the live Anthropic
org cap — that needs a real key and production load.
"""

from __future__ import annotations

import harness.core.llm as llm_mod
from harness.core.llm import _TokenRateLimiter, estimate_input_tokens


class _FakeClock:
    """A monotonic clock we advance by hand, so waits are instant and exact."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _patch_clock(monkeypatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr(llm_mod.time, "monotonic", clock)
    return clock


def test_estimate_input_tokens_scales_with_content() -> None:
    small = estimate_input_tokens("sys", [{"role": "user", "content": "hi"}])
    big = estimate_input_tokens("sys", [{"role": "user", "content": "x" * 4000}])
    assert big > small
    assert big >= 1000  # ~4000 chars / 4


async def test_disabled_limiter_never_blocks(monkeypatch) -> None:
    _patch_clock(monkeypatch)
    limiter = _TokenRateLimiter(0)
    assert limiter.enabled is False
    # Far more than any capacity; must return immediately and not raise.
    await limiter.acquire(10_000_000)
    await limiter.reconcile(10_000_000, 10_000_000)


async def test_acquire_passes_while_budget_remains(monkeypatch) -> None:
    clock = _patch_clock(monkeypatch)
    limiter = _TokenRateLimiter(30_000)
    # Three 9k calls = 27k, all under the 30k bucket — no time should pass.
    for _ in range(3):
        await limiter.acquire(9_000)
    assert clock.now == 1000.0  # no awaited sleep advanced our manual clock


async def test_acquire_blocks_until_refill(monkeypatch) -> None:
    clock = _patch_clock(monkeypatch)
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        # Model real time passing: advance the clock so the bucket refills.
        slept.append(seconds)
        clock.advance(seconds)

    monkeypatch.setattr(llm_mod.asyncio, "sleep", fake_sleep)

    limiter = _TokenRateLimiter(30_000)  # refills 500 tokens/sec
    await limiter.acquire(30_000)  # drains the bucket to 0
    await limiter.acquire(15_000)  # must now wait ~30s for 15k to refill
    assert slept, "second acquire should have had to wait"
    assert sum(slept) >= 29.0  # 15_000 / 500 = 30s of refill


async def test_reconcile_overspend_applies_backpressure(monkeypatch) -> None:
    clock = _patch_clock(monkeypatch)
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)
        clock.advance(seconds)

    monkeypatch.setattr(llm_mod.asyncio, "sleep", fake_sleep)

    limiter = _TokenRateLimiter(30_000)
    # Estimate small, but the call really cost 30k — reconcile must drain the
    # difference so the bucket goes negative and the next call waits.
    await limiter.acquire(1_000)
    await limiter.reconcile(1_000, 30_000)
    await limiter.acquire(1_000)
    assert slept, "after a big overspend the next call must wait for refill"
