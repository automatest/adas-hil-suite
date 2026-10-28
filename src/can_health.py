"""CAN fault-state & message-timing models (Exercise 12).

Two interview-relevant HIL topics:

1. CAN bus-off detection/recovery driven by a Transmit Error Counter (TEC),
   per the CAN standard: TEC >= 128 -> error-passive, TEC >= 256 -> bus-off.
2. Message-timing monitoring: cycle period, bounded jitter, and
   staleness/timeout detection.

Timing is tested with injected synthetic timestamps (float seconds, like
``time.monotonic()``) so jitter/staleness logic is deterministic and instant
— no real sleeps.
"""

from __future__ import annotations

import time
from enum import IntEnum


class BusState(IntEnum):
    ERROR_ACTIVE = 0  # normal
    ERROR_PASSIVE = 1  # degraded, still transmitting
    BUS_OFF = 2  # disconnected, must recover


class CanController:
    """Models CAN error-state transitions driven by a TEC.

    Per the CAN standard: ``TEC >= 128`` -> error-passive, ``TEC >= 256`` ->
    bus-off. Recovery requires a controller reset and observing 128
    occurrences of 11 recessive bits before rejoining; here we model it as an
    explicit :meth:`recover` with a latency window.
    """

    PASSIVE_THRESHOLD = 128
    BUSOFF_THRESHOLD = 256
    RECOVERY_LATENCY_MS = 100

    def __init__(self) -> None:
        self._tec = 0
        self._recovering_until: float | None = None

    def report_tx_error(self, n: int = 1) -> None:
        self._tec += 8 * n  # each error bumps TEC by 8 per spec

    def report_tx_success(self) -> None:
        if self._tec > 0:
            self._tec -= 1

    @property
    def state(self) -> BusState:
        if self._recovering_until and time.monotonic() < self._recovering_until:
            return BusState.BUS_OFF
        if self._tec >= self.BUSOFF_THRESHOLD:
            return BusState.BUS_OFF
        if self._tec >= self.PASSIVE_THRESHOLD:
            return BusState.ERROR_PASSIVE
        return BusState.ERROR_ACTIVE

    def recover(self) -> None:
        """Initiate bus-off recovery; completes after RECOVERY_LATENCY_MS."""
        self._recovering_until = time.monotonic() + self.RECOVERY_LATENCY_MS / 1000.0
        self._tec = 0

    def is_recovered(self) -> bool:
        return (
            self._recovering_until is not None
            and time.monotonic() >= self._recovering_until
        )


class PeriodicSignalMonitor:
    """Checks a signal arrives on its cycle with bounded jitter.

    Flags the signal STALE if no update arrives within the timeout. Mirrors
    how a receiver detects a dropped transmitter (E2E / timeout monitoring).
    """

    def __init__(self, period_ms: float, jitter_tol_ms: float, timeout_ms: float) -> None:
        self.period_ms = period_ms
        self.jitter_tol_ms = jitter_tol_ms
        self.timeout_ms = timeout_ms
        self._timestamps: list[float] = []

    def on_message(self, t: float | None = None) -> None:
        self._timestamps.append(t if t is not None else time.monotonic())

    def cycle_deltas_ms(self) -> list[float]:
        ts = self._timestamps
        return [(ts[i] - ts[i - 1]) * 1000.0 for i in range(1, len(ts))]

    def jitter_ok(self) -> bool:
        return all(
            abs(d - self.period_ms) <= self.jitter_tol_ms
            for d in self.cycle_deltas_ms()
        )

    def is_stale(self, now: float | None = None) -> bool:
        if not self._timestamps:
            return True
        now = now if now is not None else time.monotonic()
        return (now - self._timestamps[-1]) * 1000.0 > self.timeout_ms
