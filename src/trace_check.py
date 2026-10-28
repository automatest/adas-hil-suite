"""Requirement-to-test traceability validator + CI release gate.

Phase 4 (Ex17) built the validator: it loads the traceability matrix
(requirement -> test case -> test function -> status) and enforces its
integrity the way a real traceability tool (Polarion/JAMA) or a CI release
gate would:

  * flag UNCOVERED requirements (no linked test case / function),
  * flag FAILING requirements (linked test last ran FAIL),
  * report per-ASIL covered/total,
  * block the release while any ASIL C / D / B(D) requirement is uncovered
    or any test fails.

Phase 5 (Ex21) adds the CI bridge: ``update_status_from_junit`` maps each
``<testcase>`` in a pytest JUnit report back to its matrix row, and ``main``
turns the gate into a blocking CLI step — it prints ``::error::`` workflow
annotations naming the offending requirement IDs and exits non-zero so the
CI job (and, under branch protection, the merge) is blocked.

Run the tests with:

    pytest tests/test_traceability.py -v

Run the gate against a fresh pytest run:

    pytest -m "stub" --junitxml=results.xml
    python -m src.trace_check traceability/trace_matrix.csv results.xml
"""

from __future__ import annotations

import csv
import os
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass


@dataclass
class TraceRow:
    """One requirement-coverage pair from the matrix."""

    requirement_id: str
    asil: str
    test_case_id: str
    test_function: str
    status: str


def load_matrix(path: str) -> list[TraceRow]:
    """Parse the CSV matrix into TraceRow records (one per data row)."""
    with open(path, newline="") as f:
        return [TraceRow(**row) for row in csv.DictReader(f)]


def uncovered_requirements(rows: list[TraceRow]) -> list[str]:
    """A requirement is uncovered if it has no test_case_id or no test_function."""
    return [
        r.requirement_id
        for r in rows
        if not r.test_case_id.strip() or not r.test_function.strip()
    ]


def failing_requirements(rows: list[TraceRow]) -> list[str]:
    """Requirements whose linked test last reported FAIL."""
    return [r.requirement_id for r in rows if r.status.upper() == "FAIL"]


def asil_coverage(rows: list[TraceRow]) -> dict[str, dict[str, int]]:
    """Per-ASIL covered/total.

    A release gate commonly requires 100% coverage for the higher ASILs
    (C, D, and decomposed B(D) elements that still carry D intent).
    """
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        bucket = out.setdefault(r.asil, {"covered": 0, "total": 0})
        bucket["total"] += 1
        if r.test_case_id.strip() and r.test_function.strip():
            bucket["covered"] += 1
    return out


def _is_high_asil(asil: str) -> bool:
    """True for ASIL C, D, or a decomposed element that retains D intent, e.g. B(D)."""
    a = asil.upper().strip()
    # C / Cx and D / Dx cover plain ASIL C and D.
    if a.startswith(("C", "D")):
        return True
    # Decomposed elements such as B(D) or A(D) keep the original (D) integrity
    # intent in parentheses, so they must be gated at the original level.
    if "(D)" in a or "(C)" in a:
        return True
    return False


def release_gate_ok(rows: list[TraceRow]) -> bool:
    """Gate: no FAILs, and every high-ASIL (C/D/B(D)) requirement covered."""
    if failing_requirements(rows):
        return False
    for asil, cov in asil_coverage(rows).items():
        if _is_high_asil(asil) and cov["covered"] != cov["total"]:
            return False
    return True


def update_status_from_junit(rows: list[TraceRow], junit_path: str) -> list[TraceRow]:
    """Set each row's status from the JUnit result of its linked test_function.

    Parses the pytest JUnit XML, builds ``{testcase name: PASS|FAIL}`` (a
    ``<failure>`` or ``<error>`` child means FAIL), then updates the status of
    every matrix row whose ``test_function`` ran. Rows whose test_function is
    absent from the report (e.g. the deliberately uncovered requirement, or a
    test not selected by the marker filter) are left untouched, so a coverage
    gap is still caught by :func:`uncovered_requirements`.

    Mutates and returns ``rows`` for convenience.
    """
    tree = ET.parse(junit_path)
    outcomes: dict[str, str] = {}
    for tc in tree.iter("testcase"):
        name = tc.attrib.get("name", "")
        failed = any(child.tag in ("failure", "error") for child in tc)
        outcomes[name] = "FAIL" if failed else "PASS"
    for r in rows:
        if r.test_function and r.test_function in outcomes:
            r.status = outcomes[r.test_function]
    return rows


def main(argv: list[str] | None = None) -> int:
    """CLI release gate: ``trace_check <matrix.csv> [results.xml]``.

    Loads the matrix, optionally overlays live pytest results from a JUnit
    file, reports per-ASIL coverage, emits ``::error::`` workflow annotations
    for any uncovered or failing requirement, and returns a non-zero exit code
    (failing the CI job) when the release gate is not satisfied.
    """
    argv = sys.argv[1:] if argv is None else argv
    matrix = argv[0] if len(argv) > 0 else "traceability/trace_matrix.csv"
    junit = argv[1] if len(argv) > 1 else "results.xml"

    rows = load_matrix(matrix)
    # Overlay live results when a JUnit report is available; otherwise fall
    # back to the status recorded in the matrix.
    if os.path.exists(junit):
        update_status_from_junit(rows, junit)
    else:
        print(f"::warning::JUnit report '{junit}' not found; using matrix status as-is")

    print("ASIL coverage:")
    for asil, cov in sorted(asil_coverage(rows).items()):
        print(f"  {asil:<6} {cov['covered']}/{cov['total']} covered")

    gaps = uncovered_requirements(rows)
    fails = failing_requirements(rows)
    if gaps:
        print(f"::error::Uncovered requirements: {gaps}")
    if fails:
        print(f"::error::Failing requirements: {fails}")

    if not release_gate_ok(rows):
        print("::error::RELEASE GATE FAILED — safety-critical requirement unverified")
        return 1
    print("Release gate passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
