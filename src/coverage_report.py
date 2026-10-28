"""Exercise 22 — per-build requirement coverage report.

Renders a human-readable Markdown report from the traceability matrix:
overall requirement coverage %, a per-ASIL covered/total table, and the
explicit list of uncovered requirements. High-ASIL rows (C / D / decomposed
B(D)) that are not fully covered are flagged with a warning so the eye lands
on the safety-relevant gap first.

This is the artifact an auditor or lead actually reads each build. It reuses
the Phase 4 validator (``trace_check``) so the numbers here and the numbers
the release gate acts on cannot drift apart.

    python -m src.coverage_report traceability/trace_matrix.csv
"""

from __future__ import annotations

import sys

from src.trace_check import (
    _is_high_asil,
    asil_coverage,
    load_matrix,
    uncovered_requirements,
)


def render_markdown(matrix_path: str) -> str:
    """Render the coverage report for ``matrix_path`` as a Markdown string."""
    rows = load_matrix(matrix_path)
    cov = asil_coverage(rows)
    total = len(rows)
    covered = sum(
        1 for r in rows if r.test_case_id.strip() and r.test_function.strip()
    )
    pct = 100.0 * covered / total if total else 0.0

    lines = [
        "## ADAS Requirement Coverage",
        f"**Overall:** {covered}/{total} requirements covered ({pct:.0f}%)",
        "",
        "| ASIL | Covered | Total | Coverage |",
        "|---|---|---|---|",
    ]
    for asil in sorted(cov):
        c = cov[asil]
        p = 100.0 * c["covered"] / c["total"] if c["total"] else 0.0
        # Flag any high-ASIL (C / D / B(D)) bucket that is not fully covered.
        flag = " ⚠️" if _is_high_asil(asil) and c["covered"] != c["total"] else ""
        lines.append(f"| {asil} | {c['covered']} | {c['total']} | {p:.0f}%{flag} |")

    gaps = uncovered_requirements(rows)
    lines += ["", f"**Uncovered:** {', '.join(gaps) if gaps else 'none ✅'}"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else "traceability/trace_matrix.csv"
    print(render_markdown(path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
