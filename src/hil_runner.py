"""Generic HIL test runner (Exercise 9b).

Implements the stimulus -> settle -> readback -> assert loop. The runner is
a generic engine: test sequences are declarative data (:class:`TestStep`),
and the transport is an injectable :class:`BusInterface`. The runner has no
import of any concrete bus, which is what makes it backend-agnostic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .bus_interface import BusInterface


@dataclass
class TestStep:
    """One declarative HIL step: inject, settle, verify."""

    description: str
    stimulus: dict[str, float]  # signals to inject
    expected: dict[str, float]  # signals to verify
    tolerance: dict[str, float] = field(default_factory=dict)  # per-signal +/-
    settle_ms: int = 10  # wait before reading back


@dataclass
class StepResult:
    """Outcome of running a single :class:`TestStep`."""

    description: str
    passed: bool
    expected: dict[str, float]
    actual: dict[str, float]
    deviations: dict[str, float]  # signal -> |actual - expected|


class HILTestRunner:
    """Generic stimulus/settle/readback/assert engine.

    Depends only on :class:`BusInterface`; swap the backend and the same
    sequences run on real hardware.
    """

    def __init__(self, bus: BusInterface) -> None:
        self.bus = bus

    def run_step(self, step: TestStep) -> StepResult:
        self.bus.send_signals(step.stimulus)
        time.sleep(step.settle_ms / 1000.0)
        actual = self.bus.read_signals(list(step.expected.keys()))

        deviations: dict[str, float] = {}
        passed = True
        for sig, exp in step.expected.items():
            dev = abs(actual.get(sig, float("nan")) - exp)
            deviations[sig] = dev
            tol = step.tolerance.get(sig, 0.0)
            # NaN-safe: a missing signal yields NaN, and NaN <= tol is False,
            # so the step fails cleanly rather than raising.
            if not (dev <= tol):
                passed = False

        return StepResult(step.description, passed, step.expected, actual, deviations)

    def run_sequence(self, steps: list[TestStep]) -> list[StepResult]:
        # Preserves order: one StepResult per step, in sequence.
        return [self.run_step(s) for s in steps]
