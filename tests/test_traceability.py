"""Exercise 17 — tests for the traceability-matrix validator.

These tests verify the *process tool* itself: that it loads the matrix, finds
the deliberate gap (TSR_AEB_03a), flags failures, counts per-ASIL coverage,
and that the release gate blocks on an open ASIL-D/B(D) requirement and
passes only when the matrix is complete.

    TC_TRACE_001  Matrix loads               -> all rows parsed into TraceRow
    TC_TRACE_002  Gap detection              -> TSR_AEB_03a reported uncovered
    TC_TRACE_003  Fail detection             -> a FAIL row is flagged
    TC_TRACE_004  ASIL coverage counts       -> D bucket total/covered correct
    TC_TRACE_005  Release gate blocks on gap -> False while B(D) row uncovered
    TC_TRACE_006  Gate passes when complete  -> fill the gap -> gate True
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

# Traceability validator: software-only, part of the nightly regression.
pytestmark = [pytest.mark.stub, pytest.mark.regression]

from src.trace_check import (
    TraceRow,
    asil_coverage,
    failing_requirements,
    load_matrix,
    release_gate_ok,
    uncovered_requirements,
)

MATRIX = str(Path(__file__).parents[1] / "traceability" / "trace_matrix.csv")


@pytest.fixture
def rows() -> list[TraceRow]:
    return load_matrix(MATRIX)


# --- TC_TRACE_001 ----------------------------------------------------------
def test_matrix_loads(rows):
    """Every CSV data row parses into a TraceRow with all five fields."""
    assert len(rows) == 7
    assert all(isinstance(r, TraceRow) for r in rows)
    first = rows[0]
    assert first.requirement_id == "SG_AEB_01"
    assert first.asil == "D"
    assert first.test_case_id == "TC_AEB_001"
    assert first.test_function == "test_req_aeb_approach_and_brake_scenario"
    assert first.status == "PASS"


# --- TC_TRACE_002 ----------------------------------------------------------
def test_gap_detected(rows):
    """The deliberately uncovered decomposed requirement is reported."""
    uncovered = uncovered_requirements(rows)
    assert uncovered == ["TSR_AEB_03a"]


# --- TC_TRACE_003 ----------------------------------------------------------
def test_fail_detected(rows):
    """A row whose status is FAIL is flagged as failing."""
    # Baseline: nothing fails in the shipped matrix.
    assert failing_requirements(rows) == []
    # Inject a FAIL and confirm it is caught.
    mutated = [replace(rows[0], status="FAIL")] + rows[1:]
    assert failing_requirements(mutated) == ["SG_AEB_01"]


# --- TC_TRACE_004 ----------------------------------------------------------
def test_asil_coverage(rows):
    """Per-ASIL covered/total counts are correct, incl. the uncovered B(D)."""
    cov = asil_coverage(rows)
    # Five ASIL-D rows, all covered:
    # SG_AEB_01, TSR_AEB_01a, TSR_AEB_01b, FSR_AEB_03, SG_AEB_02.
    assert cov["D"] == {"covered": 5, "total": 5}
    # One ASIL-B row, covered.
    assert cov["B"] == {"covered": 1, "total": 1}
    # One B(D) row, uncovered -> covered 0 of 1.
    assert cov["B(D)"] == {"covered": 0, "total": 1}


# --- TC_TRACE_005 ----------------------------------------------------------
@pytest.mark.smoke
def test_gate_blocks_on_gap(rows):
    """Release gate blocks while an ASIL B(D) requirement is uncovered."""
    assert release_gate_ok(rows) is False


# --- TC_TRACE_006 ----------------------------------------------------------
def test_gate_passes_when_complete(rows):
    """Filling the gap (on a copy) flips the gate to True."""
    fixed = [
        replace(r, test_case_id="TC_AEB_006", test_function="test_radar_confirms_target", status="PASS")
        if r.requirement_id == "TSR_AEB_03a"
        else r
        for r in rows
    ]
    assert uncovered_requirements(fixed) == []
    assert release_gate_ok(fixed) is True
