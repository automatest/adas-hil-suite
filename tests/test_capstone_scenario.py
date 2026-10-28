"""Exercise 13 (Capstone) — end-to-end HIL scenario + JUnit traceability.

The "Approach and brake" scenario is authored purely as declarative data (a
list of TestStep). It runs through the generic HILTestRunner from Ex9
unchanged. Export JUnit XML for CI with:

    pytest tests/ -v --junitxml=results.xml

Each test function name here carries a requirement/test ID (REQ_AEB_*) so the
resulting <testcase> names are traceable in the report.
"""

from __future__ import annotations

import pytest

from src.bus_interface import StubBus
from src.hil_runner import HILTestRunner, TestStep

# Capstone scenario: software-stub tier, part of both the nightly regression
# and the fast per-PR smoke subset (it is the headline end-to-end scenario).
pytestmark = [pytest.mark.stub, pytest.mark.regression]

# Declarative scenario — data, not code. A non-programmer could edit this
# table. The same list runs on the stub in CI and on real hardware by
# swapping only the bus backend.
SCENARIO = [
    TestStep(
        "Approach — safe distance",
        stimulus={"EgoSpeed": 80, "TargetDistance": 50},
        expected={"BrakeCmd": 0.0},
        tolerance={"BrakeCmd": 0.01},
    ),
    TestStep(
        "Close in — partial brake",
        stimulus={"EgoSpeed": 80, "TargetDistance": 25},
        expected={"BrakeCmd": 0.5},
        tolerance={"BrakeCmd": 0.01},
    ),
    TestStep(
        "Imminent — full brake",
        stimulus={"EgoSpeed": 80, "TargetDistance": 5},
        expected={"BrakeCmd": 1.0},
        tolerance={"BrakeCmd": 0.01},
    ),
]


@pytest.mark.smoke
def test_req_aeb_approach_and_brake_scenario():
    """REQ_AEB_APPROACH_BRAKE — full declarative scenario runs green.

    Runs the data-defined SCENARIO through the generic runner and asserts
    every step passed.
    """
    runner = HILTestRunner(StubBus())
    results = runner.run_sequence(SCENARIO)

    failed = [r for r in results if not r.passed]
    assert not failed, f"Failed steps: {[r.description for r in failed]}"
    # One result per declared step, in order.
    assert len(results) == len(SCENARIO)
    assert [r.description for r in results] == [s.description for s in SCENARIO]
