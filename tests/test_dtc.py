"""Exercise 11 — DTC logging on invalid input.

Covers TC_DTC_001..007. Each assertion checks the *specific* DTC code, not
merely "some DTC is set". Includes the inclusive boundary (TC_DTC_007), the
stateful stuck-signal detection (TC_DTC_005), and the clear path (TC_DTC_006).
"""

from __future__ import annotations

import pytest

from src.dtc_ecu import DiagnosticECU

# DTC logging: software-stub tier, part of the nightly regression.
pytestmark = [pytest.mark.stub, pytest.mark.regression]

SPEED_RANGE_CODE = DiagnosticECU.DTC_SPEED_RANGE[0]  # "C1A00"
CONF_RANGE_CODE = DiagnosticECU.DTC_CONF_RANGE[0]  # "C1A01"
STUCK_CODE = DiagnosticECU.DTC_SIGNAL_STUCK[0]  # "C1A02"


# --- TC_DTC_001 ------------------------------------------------------------
def test_tc_dtc_001_valid_input_no_dtc():
    """Plausible speed and confidence set no DTCs."""
    ecu = DiagnosticECU()
    ecu.inject({"EgoSpeed": 50.0, "LaneConfidence": 0.8})
    assert ecu.get_active_dtcs() == []


# --- TC_DTC_002 ------------------------------------------------------------
@pytest.mark.smoke
def test_tc_dtc_002_speed_above_max():
    """EgoSpeed above max trips C1A00 specifically."""
    ecu = DiagnosticECU()
    ecu.inject({"EgoSpeed": 400.0})
    assert SPEED_RANGE_CODE in ecu.get_active_dtcs()


# --- TC_DTC_003 ------------------------------------------------------------
def test_tc_dtc_003_negative_speed():
    """Negative EgoSpeed trips C1A00 specifically."""
    ecu = DiagnosticECU()
    ecu.inject({"EgoSpeed": -5.0})
    assert SPEED_RANGE_CODE in ecu.get_active_dtcs()


# --- TC_DTC_004 ------------------------------------------------------------
def test_tc_dtc_004_confidence_above_one():
    """LaneConfidence > 1.0 trips C1A01 specifically — not the speed DTC."""
    ecu = DiagnosticECU()
    ecu.inject({"LaneConfidence": 1.5})
    active = ecu.get_active_dtcs()
    assert CONF_RANGE_CODE in active
    assert SPEED_RANGE_CODE not in active


# --- TC_DTC_005 (stateful) -------------------------------------------------
def test_tc_dtc_005_stuck_signal_over_multiple_cycles():
    """Same non-zero speed over 5 cycles trips the stuck DTC (C1A02).

    Stateful: a single frame must NOT trip it — it takes a full window.
    """
    ecu = DiagnosticECU()
    # Four identical frames: not yet stuck (window is 5).
    for _ in range(4):
        ecu.inject({"EgoSpeed": 42.0})
    assert STUCK_CODE not in ecu.get_active_dtcs()
    # Fifth identical frame completes the window -> stuck.
    ecu.inject({"EgoSpeed": 42.0})
    assert STUCK_CODE in ecu.get_active_dtcs()


# --- TC_DTC_006 ------------------------------------------------------------
def test_tc_dtc_006_clear_restores_clean_state():
    """clear_dtcs() returns to an empty, clean state."""
    ecu = DiagnosticECU()
    ecu.inject({"EgoSpeed": 400.0})  # set a DTC
    assert ecu.get_active_dtcs() != []
    ecu.clear_dtcs()
    assert ecu.get_active_dtcs() == []
    # History is also cleared: a fresh stuck run starts from scratch.
    for _ in range(5):
        ecu.inject({"EgoSpeed": 10.0})
    assert STUCK_CODE in ecu.get_active_dtcs()


# --- TC_DTC_007 (inclusive boundary) ---------------------------------------
def test_tc_dtc_007_boundary_exactly_at_max_no_dtc():
    """EgoSpeed exactly at the max is valid — inclusive range, no off-by-one."""
    ecu = DiagnosticECU()
    ecu.inject({"EgoSpeed": DiagnosticECU.SPEED_MAX})  # 300.0
    assert SPEED_RANGE_CODE not in ecu.get_active_dtcs()

    # Lower boundary and confidence boundaries are inclusive too.
    ecu2 = DiagnosticECU()
    ecu2.inject({"EgoSpeed": DiagnosticECU.SPEED_MIN,
                 "LaneConfidence": DiagnosticECU.CONFIDENCE_MAX})
    assert ecu2.get_active_dtcs() == []
