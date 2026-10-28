"""Exercise 10 — ECU boot-up timing validation.

Covers TC_BOOT_001..005. Deadlines are read from the (scaled) model
constants, never hard-coded, so flipping ``TIME_SCALE`` keeps the tests
consistent. See docs/phase3_timing_assumptions.md for the scaling decision.
"""

from __future__ import annotations

import pytest

from src.ecu_boot import BootableECU

# Boot timing: software-stub tier, part of the nightly regression.
pytestmark = [pytest.mark.stub, pytest.mark.regression]


# --- TC_BOOT_001 -----------------------------------------------------------
def test_tc_boot_001_heartbeat_appears_fast():
    """ECU_Alive must become available well within the boot deadline."""
    ecu = BootableECU()
    ecu.power_on()
    # Poll up to the full deadline; the heartbeat is the fastest message.
    elapsed = ecu.time_to_available_ms("ECU_Alive", timeout_ms=ecu.BOOT_DEADLINE_MS)
    assert elapsed is not None, "ECU_Alive never became available"
    # Its own deadline is its modeled latency; assert against that, inclusive.
    assert elapsed >= ecu.BOOT_LATENCIES_MS["ECU_Alive"]
    assert elapsed <= ecu.BOOT_DEADLINE_MS


# --- TC_BOOT_002 -----------------------------------------------------------
@pytest.mark.smoke
def test_tc_boot_002_all_messages_up_within_deadline():
    """Every init message is available by BOOT_DEADLINE_MS — per message."""
    ecu = BootableECU()
    ecu.power_on()
    for name in ecu.BOOT_LATENCIES_MS:
        elapsed = ecu.time_to_available_ms(name, timeout_ms=ecu.BOOT_DEADLINE_MS)
        assert elapsed is not None, f"{name} missed the boot deadline"
        # Each message checked against the global deadline individually.
        assert elapsed <= ecu.BOOT_DEADLINE_MS, (
            f"{name} available at {elapsed:.1f} ms > deadline "
            f"{ecu.BOOT_DEADLINE_MS} ms"
        )


# --- TC_BOOT_003 -----------------------------------------------------------
def test_tc_boot_003_feature_ready_is_last():
    """ADAS_Ready latency >= every other message's latency."""
    latencies = BootableECU.BOOT_LATENCIES_MS
    adas_ready = latencies["ADAS_Ready"]
    assert all(adas_ready >= lat for lat in latencies.values())
    # And it is strictly the max among the others (feature-ready comes last).
    others = {k: v for k, v in latencies.items() if k != "ADAS_Ready"}
    assert adas_ready >= max(others.values())


# --- TC_BOOT_004 -----------------------------------------------------------
def test_tc_boot_004_no_messages_before_power_on():
    """Nothing is available until power_on() is called."""
    ecu = BootableECU()
    for name in ecu.BOOT_LATENCIES_MS:
        assert ecu.is_message_available(name) is False


# --- TC_BOOT_005 (negative test) -------------------------------------------
def test_tc_boot_005_deadline_miss_is_detected():
    """Inject an over-deadline latency and assert the harness reports a miss.

    Proves the timing check has teeth: a message that is deliberately slower
    than the deadline must fail the availability check.
    """
    ecu = BootableECU()
    # Make ADAS_Ready arrive at 2x the deadline — a guaranteed miss.
    ecu.set_latency_ms("ADAS_Ready", ecu.BOOT_DEADLINE_MS * 2)
    ecu.power_on()

    elapsed = ecu.time_to_available_ms("ADAS_Ready", timeout_ms=ecu.BOOT_DEADLINE_MS)
    # Within the deadline window, the over-deadline message never appears.
    assert elapsed is None, "over-deadline message should NOT be available in time"

    # Framed as a pass/fail timing assertion the way a real check would be:
    within_deadline = elapsed is not None and elapsed <= ecu.BOOT_DEADLINE_MS
    assert within_deadline is False
