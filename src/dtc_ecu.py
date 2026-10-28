"""Diagnostic Trouble Code (DTC) model (Exercise 11).

Models how a real ECU raises a trouble code when a signal is implausible,
stuck, or out of its valid physical range. Range checks are inclusive at the
boundary; stuck detection is stateful over a sliding window.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DTC:
    """A single diagnostic trouble code."""

    code: str  # e.g. "C1A00"
    description: str
    active: bool = True


class DiagnosticECU:
    """ECU with simple range-checking that sets DTCs on invalid input."""

    SPEED_MIN, SPEED_MAX = 0.0, 300.0  # kph plausible range
    CONFIDENCE_MIN, CONFIDENCE_MAX = 0.0, 1.0

    DTC_SPEED_RANGE = ("C1A00", "EgoSpeed out of plausible range")
    DTC_CONF_RANGE = ("C1A01", "LaneConfidence out of [0,1] range")
    DTC_SIGNAL_STUCK = ("C1A02", "Signal stuck — no change over N cycles")

    def __init__(self) -> None:
        self._dtcs: dict[str, DTC] = {}
        self._speed_history: list[float] = []

    def inject(self, signals: dict[str, float]) -> None:
        if "EgoSpeed" in signals:
            v = signals["EgoSpeed"]
            if not (self.SPEED_MIN <= v <= self.SPEED_MAX):
                self._set(*self.DTC_SPEED_RANGE)
            self._speed_history.append(v)
            self._check_stuck()
        if "LaneConfidence" in signals:
            c = signals["LaneConfidence"]
            if not (self.CONFIDENCE_MIN <= c <= self.CONFIDENCE_MAX):
                self._set(*self.DTC_CONF_RANGE)

    def _check_stuck(self, window: int = 5) -> None:
        h = self._speed_history
        if len(h) >= window and len(set(h[-window:])) == 1 and h[-1] > 0:
            self._set(*self.DTC_SIGNAL_STUCK)

    def _set(self, code: str, desc: str) -> None:
        self._dtcs[code] = DTC(code, desc, active=True)

    def get_active_dtcs(self) -> list[str]:
        return [c for c, d in self._dtcs.items() if d.active]

    def clear_dtcs(self) -> None:
        self._dtcs.clear()
        self._speed_history.clear()
