"""Phase 5 pytest configuration — the bench/hardware tier gate.

The suite is tiered by marker (see ``pyproject.toml``):

  * ``stub``  — software StubBus; runs on any machine (cloud runner, laptop).
  * ``bench`` — needs a real ECU wired over CAN; runs only on a self-hosted
                runner physically connected to the hardware.

A cloud runner (and your laptop) has no bench hardware, so ``bench`` tests
must *skip*, not error. Hardware presence is signalled by the ``HIL_BENCH``
environment variable, which a real self-hosted ``[self-hosted, hil-bench]``
runner would set. The ``hil_bus`` fixture is the single gate: any ``bench``
test that takes it is skipped automatically when no hardware is present, so
the same suite runs green on a laptop, a cloud VM, and a wired bench.
"""

from __future__ import annotations

import os

import pytest


def hil_hardware_present() -> bool:
    """True only on a runner wired to real HIL hardware.

    Driven by the ``HIL_BENCH`` env var set on the self-hosted bench runner.
    Returns False on laptops and cloud runners, so ``bench`` tests skip.
    """
    return os.environ.get("HIL_BENCH", "") == "1"


@pytest.fixture
def hil_bus():
    """Provide a real CAN-backed BusInterface, or skip if no hardware.

    On the bench this would construct a ``python-can`` backed implementation
    of the Phase 3 ``BusInterface`` (same interface as ``StubBus``), so the
    identical HIL test sequences run against a real ECU. Off-bench it skips
    cleanly rather than erroring.
    """
    if not hil_hardware_present():
        pytest.skip("no HIL hardware on this runner (set HIL_BENCH=1 on the bench)")
    # On a real bench, return a python-can backed BusInterface here. Kept as a
    # guarded stub in the practice repo since no hardware is wired.
    raise NotImplementedError("wire a python-can BusInterface here on the bench runner")
