"""ECU boot-up timing model (Exercise 10).

TIMING SCALING DECISION
-----------------------
Real ADAS boot deadlines are in the hundreds of milliseconds. A suite that
literally sleeps ~500 ms per case is slow, so for fast, deterministic tests
this module scales every latency and the global deadline DOWN BY 10x
(``TIME_SCALE = 0.1``). The *relative* ordering and margins are preserved,
so the timing logic under test is identical; only the wall-clock duration
shrinks (~50 ms worst case instead of ~500 ms).

The real, unscaled values are documented in ``BOOT_LATENCIES_MS_REAL`` and
``BOOT_DEADLINE_MS_REAL`` below. To run against true hardware deadlines, set
``TIME_SCALE = 1.0``. See ``docs/phase3_timing_assumptions.md``.
"""

from __future__ import annotations

import time

# Scale factor applied to all boot timings. 0.1 => 10x faster tests.
TIME_SCALE = 0.1


class BootableECU:
    """Models an ECU boot sequence with per-message availability deadlines.

    After :meth:`power_on`, each init message becomes 'available' once its
    simulated latency has elapsed. Tests assert availability within spec.
    """

    # Real, unscaled values (documentation / hardware reference).
    BOOT_LATENCIES_MS_REAL = {
        "ECU_Alive": 50,  # heartbeat — must be fast
        "ECU_Version": 120,
        "ECU_SelfTestDone": 400,  # self-test completes
        "ADAS_Ready": 480,  # feature availability announced
    }
    BOOT_DEADLINE_MS_REAL = 500  # everything must be up within 500 ms

    # Scaled values actually used by the runtime model and the tests.
    BOOT_LATENCIES_MS = {
        name: latency * TIME_SCALE for name, latency in BOOT_LATENCIES_MS_REAL.items()
    }
    BOOT_DEADLINE_MS = BOOT_DEADLINE_MS_REAL * TIME_SCALE

    def __init__(self) -> None:
        self._power_on_at: float | None = None
        # Allow per-instance latency overrides (used by the negative test to
        # inject an over-deadline latency without mutating class state).
        self._latencies_ms: dict[str, float] = dict(self.BOOT_LATENCIES_MS)

    def set_latency_ms(self, name: str, latency_ms: float) -> None:
        """Override the simulated latency for one message (ms, scaled units)."""
        self._latencies_ms[name] = latency_ms

    def power_on(self) -> None:
        self._power_on_at = time.monotonic()

    def is_message_available(self, name: str) -> bool:
        if self._power_on_at is None:
            return False
        elapsed_ms = (time.monotonic() - self._power_on_at) * 1000.0
        return elapsed_ms >= self._latencies_ms.get(name, float("inf"))

    def time_to_available_ms(self, name: str, timeout_ms: float) -> float | None:
        """Poll until the message is available or timeout.

        Returns the elapsed milliseconds until availability, or ``None`` if
        the message never appeared within ``timeout_ms``.
        """
        if self._power_on_at is None:
            self.power_on()
        assert self._power_on_at is not None
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            if self.is_message_available(name):
                return (time.monotonic() - self._power_on_at) * 1000.0
            time.sleep(0.001)
        return None
