"""Exercise 22 — tests for the per-build coverage report.

Verifies the report generator itself: that it computes the right overall
coverage %, renders a per-ASIL table, flags the incomplete high-ASIL bucket
with a warning, and lists the deliberate uncovered requirement. Like the
Ex17 validator tests, this is a test on the *process tool*, not the product.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.coverage_report import render_markdown

# Software-only process tool; part of the nightly regression and the fast
# per-PR smoke subset (it guards the audit artifact).
pytestmark = [pytest.mark.stub, pytest.mark.regression]

MATRIX = str(Path(__file__).parents[1] / "traceability" / "trace_matrix.csv")


@pytest.fixture
def report() -> str:
    return render_markdown(MATRIX)


# --- TC_COV_001 ------------------------------------------------------------
@pytest.mark.smoke
def test_overall_percentage(report):
    """Shipped matrix is 6/7 covered -> 86%, stated in the header."""
    assert "**Overall:** 6/7 requirements covered (86%)" in report


# --- TC_COV_002 ------------------------------------------------------------
def test_per_asil_table_present(report):
    """A per-ASIL table is rendered with the fully-covered D bucket at 100%."""
    assert "| ASIL | Covered | Total | Coverage |" in report
    # Five ASIL-D rows, all covered.
    assert "| D | 5 | 5 | 100% |" in report
    # One ASIL-B row, covered.
    assert "| B | 1 | 1 | 100% |" in report


# --- TC_COV_003 ------------------------------------------------------------
def test_incomplete_high_asil_is_flagged(report):
    """The uncovered B(D) bucket (0/1) is flagged with a warning."""
    assert "| B(D) | 0 | 1 | 0% ⚠️ |" in report


# --- TC_COV_004 ------------------------------------------------------------
def test_uncovered_list(report):
    """The explicit uncovered list names the deliberate gap."""
    assert "**Uncovered:** TSR_AEB_03a" in report


# --- TC_COV_005 ------------------------------------------------------------
def test_full_coverage_has_no_flag_and_none(tmp_path):
    """A complete matrix reports 100%, no warning flag, and 'none'."""
    complete = tmp_path / "complete.csv"
    complete.write_text(
        "requirement_id,asil,test_case_id,test_function,status\n"
        "SG_AEB_01,D,TC_AEB_001,test_req_aeb_approach_and_brake_scenario,PASS\n"
        "TSR_AEB_03a,B(D),TC_AEB_006,test_radar_confirms_target,PASS\n"
    )
    out = render_markdown(str(complete))
    assert "**Overall:** 2/2 requirements covered (100%)" in out
    assert "⚠️" not in out
    assert "**Uncovered:** none ✅" in out
