"""Exercise 12 — CAN bus-off recovery & message-timing assertions.

Covers TC_BUS_001..005 (error-state transitions / recovery) and
TC_TIME_001..004 (cycle period, jitter, staleness). Timing tests inject
synthetic timestamps so they are deterministic and instant.
"""

from __future__ import annotations

import time

import pytest

from src.can_health import BusState, CanController, PeriodicSignalMonitor

# Bus recovery & timing: software-stub tier, part of the nightly regression.
pytestmark = [pytest.mark.stub, pytest.mark.regression]


# ===========================================================================
# Bus error-state transitions & recovery
# ===========================================================================

# --- TC_BUS_001 ------------------------------------------------------------
def test_tc_bus_001_normal_to_error_passive():
    """TEC crossing the 128 threshold moves to ERROR_PASSIVE."""
    ctrl = CanController()
    assert ctrl.state is BusState.ERROR_ACTIVE
    # 16 errors * 8 = 128 -> exactly at the passive threshold (inclusive).
    for _ in range(16):
        ctrl.report_tx_error()
    assert ctrl.state is BusState.ERROR_PASSIVE


# --- TC_BUS_002 ------------------------------------------------------------
@pytest.mark.smoke
def test_tc_bus_002_error_passive_to_bus_off():
    """TEC crossing the 256 threshold moves to BUS_OFF."""
    ctrl = CanController()
    # 32 errors * 8 = 256 -> exactly at the bus-off threshold (inclusive).
    for _ in range(32):
        ctrl.report_tx_error()
    assert ctrl.state is BusState.BUS_OFF


def test_tc_bus_002b_boundary_just_below_thresholds():
    """One step below each threshold stays in the lower state (boundary)."""
    # 120 (< 128) -> still error-active.
    ctrl = CanController()
    for _ in range(15):  # 15 * 8 = 120
        ctrl.report_tx_error()
    assert ctrl.state is BusState.ERROR_ACTIVE

    # 248 (< 256) -> error-passive, not yet bus-off.
    ctrl2 = CanController()
    for _ in range(31):  # 31 * 8 = 248
        ctrl2.report_tx_error()
    assert ctrl2.state is BusState.ERROR_PASSIVE


# --- TC_BUS_003 ------------------------------------------------------------
def test_tc_bus_003_recovery_in_progress_is_bus_off():
    """During the recovery latency window the state reports BUS_OFF."""
    ctrl = CanController()
    for _ in range(32):  # drive to bus-off
        ctrl.report_tx_error()
    assert ctrl.state is BusState.BUS_OFF

    ctrl.recover()  # starts the latency window
    # Immediately after recover(), still within the window -> BUS_OFF.
    assert ctrl.state is BusState.BUS_OFF
    assert ctrl.is_recovered() is False


# --- TC_BUS_004 ------------------------------------------------------------
def test_tc_bus_004_recovery_completes():
    """After the latency elapses, recovery completes and state is ACTIVE."""
    ctrl = CanController()
    for _ in range(32):
        ctrl.report_tx_error()
    ctrl.recover()
    # Wait slightly longer than the recovery latency.
    time.sleep((ctrl.RECOVERY_LATENCY_MS + 20) / 1000.0)
    assert ctrl.is_recovered() is True
    assert ctrl.state is BusState.ERROR_ACTIVE


# --- TC_BUS_005 ------------------------------------------------------------
def test_tc_bus_005_success_decrements_tec():
    """Errors then successes improve the state (TEC decremented)."""
    ctrl = CanController()
    for _ in range(16):  # TEC = 128 -> error-passive
        ctrl.report_tx_error()
    assert ctrl.state is BusState.ERROR_PASSIVE
    # One success drops TEC to 127 -> back to error-active.
    ctrl.report_tx_success()
    assert ctrl.state is BusState.ERROR_ACTIVE


# ===========================================================================
# Message-timing assertions (synthetic timestamps — deterministic & instant)
# ===========================================================================

# --- TC_TIME_001 -----------------------------------------------------------
def test_tc_time_001_on_period_low_jitter():
    """Deltas ~ period within tolerance -> jitter_ok() True."""
    mon = PeriodicSignalMonitor(period_ms=10.0, jitter_tol_ms=1.0, timeout_ms=30.0)
    # Timestamps in seconds; 10 ms apart with <= 1 ms wobble.
    for t in [0.000, 0.0101, 0.0199, 0.0300, 0.0402]:
        mon.on_message(t=t)
    deltas = mon.cycle_deltas_ms()
    assert len(deltas) == 4
    assert mon.jitter_ok() is True


# --- TC_TIME_002 (failure detection) ---------------------------------------
def test_tc_time_002_jitter_exceeds_tolerance():
    """One delta far off the period -> jitter_ok() False."""
    mon = PeriodicSignalMonitor(period_ms=10.0, jitter_tol_ms=1.0, timeout_ms=30.0)
    # Third gap is 20 ms (10 ms off a 10 ms period) -> breaches tolerance.
    for t in [0.000, 0.010, 0.020, 0.040]:
        mon.on_message(t=t)
    assert mon.jitter_ok() is False


# --- TC_TIME_003 (failure detection) ---------------------------------------
def test_tc_time_003_staleness_timeout():
    """No message within the timeout -> is_stale() True."""
    mon = PeriodicSignalMonitor(period_ms=10.0, jitter_tol_ms=1.0, timeout_ms=30.0)
    mon.on_message(t=0.000)
    # 'now' is 50 ms after the last message, timeout is 30 ms -> stale.
    assert mon.is_stale(now=0.050) is True


def test_tc_time_003b_empty_monitor_is_stale():
    """A monitor that never saw a message is stale by definition."""
    mon = PeriodicSignalMonitor(period_ms=10.0, jitter_tol_ms=1.0, timeout_ms=30.0)
    assert mon.is_stale(now=0.0) is True


# --- TC_TIME_004 -----------------------------------------------------------
def test_tc_time_004_fresh_message_not_stale():
    """A recent message within the timeout -> is_stale() False."""
    mon = PeriodicSignalMonitor(period_ms=10.0, jitter_tol_ms=1.0, timeout_ms=30.0)
    mon.on_message(t=0.100)
    # 'now' is only 5 ms after the last message -> fresh.
    assert mon.is_stale(now=0.105) is False
