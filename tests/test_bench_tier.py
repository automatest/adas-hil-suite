"""Bench tier — tests that require real HIL hardware.

These are the hardware-dependent counterparts to the ``stub`` tests: the same
HIL sequences, but run against a real ECU over CAN instead of ``StubBus``.
They are marked ``bench`` + ``regression`` and take the ``hil_bus`` fixture,
so on any machine without hardware (every cloud runner, your laptop) they
*skip* rather than error — proving the tier split is enforced by fixture, not
convention. On a ``[self-hosted, hil-bench]`` runner with ``HIL_BENCH=1`` set,
they run for real.
"""

from __future__ import annotations

import pytest

from src.hil_runner import HILTestRunner, TestStep

pytestmark = [pytest.mark.bench, pytest.mark.regression]


def test_on_real_ecu(hil_bus):
    """Run the approach-and-brake sequence against a real ECU over CAN.

    Skipped off-bench via the ``hil_bus`` fixture. On the bench, the same
    declarative sequence used by the stub capstone runs against hardware —
    the payoff of the injectable ``BusInterface`` from Phase 3.
    """
    runner = HILTestRunner(hil_bus)
    sequence = [
        TestStep(
            "Imminent — full brake",
            stimulus={"EgoSpeed": 80, "TargetDistance": 5},
            expected={"BrakeCmd": 1.0},
            tolerance={"BrakeCmd": 0.05},
        ),
    ]
    results = runner.run_sequence(sequence)
    assert all(r.passed for r in results)
