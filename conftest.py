"""What every Python test shares: one clock that only the test moves."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from backend import clock as app_clock
from backend.tests.fake_clock import CLOCK, FakeClock

# Installed at import, before any fixture or module-level window reads the time, so no test ever
# sees the real clock.
app_clock.use(CLOCK)


@pytest.fixture(autouse=True)
def every_test_starts_at_the_same_moment() -> Iterator[None]:
    CLOCK.reset()
    yield
    CLOCK.reset()


@pytest.fixture()
def clock() -> FakeClock:
    """The clock the app reads, at fake_clock.START when the test begins; move it with set or move."""
    return CLOCK
