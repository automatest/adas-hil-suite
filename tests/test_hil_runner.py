"""Exercise 9 — HIL signal-injection runner tests.

Covers TC_HIL_001..006: tolerance behaviour, NaN-safe missing-signal
handling, sequence ordering, and the backend-swap contract that proves the
runner is backend-agnostic.
"""

from __future__ import annotations

import pytest

from src.bus_interface import BusInterface, StubBus
from src.hil_runner import HILTestRunner, StepResult, TestStep

# HIL runner: software-stub tier, part of the nightly regression.
pytestmark = [pytest.mark.stub, pytest.mark.regression]


# Keep the suite fast: no real settle time is needed for the stub DUT.
FAST_SETTLE_MS = 0


def _runner() -> HILTestRunner:
    return HILTestRunner(StubBus())


# --- TC_HIL_001 ------------------------------------------------------------
@pytest.mark.smoke
def test_tc_hil_001_single_step_exact_match():
    """Step whose expected matches the DUT output exactly passes."""
    runner = _runner()
    step = TestStep(
        "exact match — partial brake",
        stimulus={"EgoSpeed": 80, "TargetDistance": 25},
        expected={"BrakeCmd": 0.5},
        tolerance={"BrakeCmd": 0.0},  # exact
        settle_ms=FAST_SETTLE_MS,
    )
    result = runner.run_step(step)
    assert result.passed is True
    assert result.actual["BrakeCmd"] == 0.5
    assert result.deviations["BrakeCmd"] == 0.0


# --- TC_HIL_002 ------------------------------------------------------------
def test_tc_hil_002_within_tolerance_passes():
    """Actual off by less than tolerance -> pass (inclusive comparison)."""
    runner = _runner()
    # DUT emits BrakeCmd=0.5; expect 0.49 with tol 0.02 -> dev 0.01 <= 0.02.
    step = TestStep(
        "within tolerance",
        stimulus={"EgoSpeed": 80, "TargetDistance": 25},
        expected={"BrakeCmd": 0.49},
        tolerance={"BrakeCmd": 0.02},
        settle_ms=FAST_SETTLE_MS,
    )
    result = runner.run_step(step)
    assert result.passed is True
    assert result.deviations["BrakeCmd"] <= step.tolerance["BrakeCmd"]


# --- TC_HIL_003 ------------------------------------------------------------
def test_tc_hil_003_outside_tolerance_fails():
    """Actual off by more than tolerance -> fail."""
    runner = _runner()
    # DUT emits BrakeCmd=0.5; expect 0.0 with tol 0.01 -> dev 0.5 > 0.01.
    step = TestStep(
        "outside tolerance",
        stimulus={"EgoSpeed": 80, "TargetDistance": 25},
        expected={"BrakeCmd": 0.0},
        tolerance={"BrakeCmd": 0.01},
        settle_ms=FAST_SETTLE_MS,
    )
    result = runner.run_step(step)
    assert result.passed is False
    assert result.deviations["BrakeCmd"] > step.tolerance["BrakeCmd"]


# --- TC_HIL_004 ------------------------------------------------------------
def test_tc_hil_004_missing_signal_fails_without_crash():
    """Reading an absent output yields NaN deviation -> fail, not raise."""
    runner = _runner()
    step = TestStep(
        "missing output signal",
        stimulus={"EgoSpeed": 10, "TargetDistance": 5},
        expected={"NonExistentSignal": 1.0},
        tolerance={"NonExistentSignal": 0.1},
        settle_ms=FAST_SETTLE_MS,
    )
    # Must not raise.
    result = runner.run_step(step)
    assert result.passed is False
    # StubBus defaults missing reads to 0.0, so dev = |0.0 - 1.0| = 1.0.
    assert result.deviations["NonExistentSignal"] == 1.0


def test_tc_hil_004_truly_missing_read_is_nan_safe():
    """A bus that omits the key entirely yields NaN dev and fails cleanly."""

    class SilentBus(BusInterface):
        """Returns an empty dict — the signal is genuinely absent."""

        def send_signals(self, signals: dict[str, float]) -> None:  # noqa: D401
            pass

        def read_signals(self, names: list[str]) -> dict[str, float]:
            return {}  # nothing comes back

    runner = HILTestRunner(SilentBus())
    step = TestStep(
        "genuinely missing read",
        stimulus={"EgoSpeed": 10},
        expected={"BrakeCmd": 1.0},
        tolerance={"BrakeCmd": 0.1},
        settle_ms=FAST_SETTLE_MS,
    )
    result = runner.run_step(step)  # NaN <= tol is False, no exception
    assert result.passed is False
    assert result.deviations["BrakeCmd"] != result.deviations["BrakeCmd"]  # NaN


# --- TC_HIL_005 ------------------------------------------------------------
def test_tc_hil_005_multi_step_sequence_preserves_order():
    """Three steps run in order; one StepResult recorded per step."""
    runner = _runner()
    sequence = [
        TestStep("safe", {"EgoSpeed": 80, "TargetDistance": 50},
                 {"BrakeCmd": 0.0}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
        TestStep("partial", {"EgoSpeed": 80, "TargetDistance": 25},
                 {"BrakeCmd": 0.5}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
        TestStep("full", {"EgoSpeed": 80, "TargetDistance": 5},
                 {"BrakeCmd": 1.0}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
    ]
    results = runner.run_sequence(sequence)
    assert len(results) == 3
    assert [r.description for r in results] == ["safe", "partial", "full"]
    assert all(isinstance(r, StepResult) for r in results)
    assert all(r.passed for r in results)


# --- TC_HIL_006 ------------------------------------------------------------
@pytest.mark.smoke
def test_tc_hil_006_backend_swap_contract():
    """Same sequence runs against a second BusInterface implementation.

    Proves the runner depends only on the interface, not a concrete bus.
    """

    class MirrorBus(BusInterface):
        """A different backend: a lookup-table 'ECU' with identical contract."""

        TABLE = {
            (80.0, 50.0): 0.0,
            (80.0, 25.0): 0.5,
            (80.0, 5.0): 1.0,
        }

        def __init__(self) -> None:
            self._state: dict[str, float] = {}

        def send_signals(self, signals: dict[str, float]) -> None:
            self._state.update(signals)
            key = (self._state.get("EgoSpeed", 0.0),
                   self._state.get("TargetDistance", 999.0))
            self._state["BrakeCmd"] = self.TABLE.get(key, 0.0)

        def read_signals(self, names: list[str]) -> dict[str, float]:
            return {n: self._state.get(n, 0.0) for n in names}

    sequence = [
        TestStep("safe", {"EgoSpeed": 80, "TargetDistance": 50},
                 {"BrakeCmd": 0.0}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
        TestStep("partial", {"EgoSpeed": 80, "TargetDistance": 25},
                 {"BrakeCmd": 0.5}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
        TestStep("full", {"EgoSpeed": 80, "TargetDistance": 5},
                 {"BrakeCmd": 1.0}, {"BrakeCmd": 0.01}, FAST_SETTLE_MS),
    ]

    # Identical sequence, two different backends — both must pass.
    stub_results = HILTestRunner(StubBus()).run_sequence(sequence)
    mirror_results = HILTestRunner(MirrorBus()).run_sequence(sequence)

    assert all(r.passed for r in stub_results)
    assert all(r.passed for r in mirror_results)
    assert [r.actual for r in stub_results] == [r.actual for r in mirror_results]
