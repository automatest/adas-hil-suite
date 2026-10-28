# Design: Phase 5 – Automation + CI/CD Integration

## Architecture Overview

Phase 5 has almost no new test logic — it is **orchestration**. Phases 1–4 produced the artifacts (CAN decode, black-box ADAS suites, an injectable-bus HIL harness, a traceability matrix + release gate). Phase 5 makes them run automatically, gate merges, and leave an audit trail per commit. The deliverable is a pipeline, not a feature.

In a safety-critical project the pipeline is the mechanism that **enforces the process**:

```
 push / PR
    │
    ▼
┌────────────────────────────────────────────────────────────┐
│  CI pipeline                                                 │
│   1. install (deterministic, pinned via pyproject)           │
│   2. run pytest  →  results.xml  (JUnit)                     │
│   3. map results → requirement IDs  →  trace_matrix status   │
│   4. GATE: trace_check.release_gate_ok()?                    │
│        - any ASIL C/D/B(D) requirement uncovered → FAIL      │
│        - any linked test FAIL → FAIL                         │
│   5. publish coverage report + results.xml as artifacts      │
│   6. (nightly) full regression; (PR) fast smoke subset       │
└────────────────────────────────────────────────────────────┘
    │
    ▼  green = mergeable, with an audit trail per commit
```

Three things this pipeline does that a generic web-app pipeline does not:

- **Traceability gating** — a merge is blocked not only by a red test but by an *unverified safety requirement*.
- **Hardware tiering** — software-stub tests (the Phase 3 `StubBus`) run on cloud runners every PR; real-bench HIL tests run on a **self-hosted runner** physically wired to hardware, on a slower cadence. The suite splits cleanly along this line via pytest markers.
- **Auditable artifacts** — every build leaves `results.xml` + a coverage report keyed to requirement IDs, retained for the safety case.

---

## Consolidation: phase5 is the Home of the Suite (Ex19)

Rather than copy Phase 3/4 files repeatedly, phase5 becomes the single consolidated project. The Phase 3 `src/` modules and the Phase 4 `trace_check.py` + `trace_matrix.csv` move in, and packaging makes them one importable project.

```
phase5/
├── .github/workflows/adas_ci.yml    ← Ex20 → Ex21 → Ex23 (final form)
├── pyproject.toml                   ← Ex19 — packaging + markers
├── conftest.py                      ← Ex19 — bench-skip fixture
├── README.md                        ← tiers + branch-protection notes
├── src/
│   ├── __init__.py
│   ├── bus_interface.py  hil_runner.py  ecu_boot.py  dtc_ecu.py  can_health.py   (phase3)
│   ├── trace_check.py               ← phase4 + Ex21 CLI/JUnit mapping
│   └── coverage_report.py           ← Ex22
├── tests/   (phase3 tests, marked) + test_traceability.py + test_coverage_report.py
└── traceability/trace_matrix.csv    ← phase4
```

The precondition for reliable CI is eliminating import fragility. Phases 3/4 relied on a root `conftest.py` inserting the project root on `sys.path`. Phase 5 replaces that with real packaging: `pip install -e ".[test]"` puts `src` on the path as an installed, editable package, so `from src.trace_check import ...` and `python -m src.trace_check` resolve identically on a laptop and a cloud runner with no shims.

```toml
[project]
name = "adas-hil-suite"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["python-can", "cantools"]

[project.optional-dependencies]
test = ["pytest", "pytest-cov"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "stub: runs against the software StubBus (cloud runner, every PR)",
    "bench: requires real HIL hardware (self-hosted runner, scheduled)",
    "smoke: fast subset for per-PR gating",
    "regression: full suite for nightly runs",
]
addopts = "-ra"
```

---

## The Marker Tier Model (Ex19)

Tiering is enforced by markers, not convention. Two orthogonal axes:

```
                 stub (software StubBus)        bench (real ECU over CAN)
smoke      ┌──────────────────────────┐   ┌──────────────────────────┐
(fast,     │ PR gate — every PR,      │   │ (rare; a fast bench check │
per PR)    │ across Python matrix     │   │  if a bench exists)       │
           └──────────────────────────┘   └──────────────────────────┘
regression ┌──────────────────────────┐   ┌──────────────────────────┐
(full,     │ nightly schedule         │   │ bench job — self-hosted   │
nightly)   │ full stub suite          │   │ [self-hosted, hil-bench]  │
           └──────────────────────────┘   └──────────────────────────┘
```

- `pytest -m "smoke and stub"` → the fast cloud-safe PR subset.
- `pytest -m "stub"` → the full stub regression (nightly).
- `pytest -m "bench"` → the hardware tier, which **skips** on any machine without hardware.

**Bench-skip fixture.** `conftest.py` detects hardware absence and skips `bench` tests rather than erroring. The same `BusInterface` abstraction from Phase 3 is the payoff: `bench` tests use a real `python-can` backend while `stub` tests use `StubBus` — identical test sequences, different bus.

```python
# conftest.py (sketch)
import pytest

def _hil_hardware_present() -> bool:
    # e.g. probe for a known CAN interface / env flag set on the bench runner
    return False  # False on laptops and cloud runners

@pytest.fixture
def hil_bus():
    if not _hil_hardware_present():
        pytest.skip("no HIL hardware on this runner")
    ...  # return a real python-can backed BusInterface on the bench
```

---

## Pipeline Evolution: Ex20 → Ex21 → Ex23

The one workflow file grows in three steps. Keeping it one file (rather than three) mirrors how a real pipeline is iterated in place.

**Ex20 — baseline.** Single `ubuntu-latest` job on Python 3.13: checkout → setup-python → `pip install -e ".[test]"` → `pytest -m "stub" --junitxml=results.xml --cov=src --cov-report=xml` → upload `results.xml` (`if: always()`) → surface a JUnit summary in the Checks tab via `dorny/test-reporter`. `if: always()` on the upload is deliberate: a failed run must still publish its report, or the audit trail has holes exactly when they matter.

**Ex21 — the gate.** A step is added after the test step that runs the extended `trace_check` CLI. Because it `exit(1)`s on a gap/fail, the job goes red and (with branch protection) the PR cannot merge. This is the safety-specific part of the pipeline — the one that distinguishes a test *engineer* from a test *writer*.

**Ex23 — final tiered form.** The job splits into three: a Python-version `pr-gate` matrix, a `nightly-regression` schedule job, and a disabled self-hosted `bench` job. Trigger selection (`if: github.event_name == ...`) routes each event to the right job.

---

## The Traceability Gate CLI (Ex21)

Phase 4 left `trace_check.py` with a `__main__` block that reads status straight from the CSV. Phase 5 adds the missing link: deriving status from the *actual* test run rather than a hand-maintained column.

```
results.xml (JUnit)          trace_matrix.csv               release gate
 <testcase name=...>   ─────▶ row.test_function match ─────▶ release_gate_ok()
 failure/error child?        row.status = PASS|FAIL           │ exit 0 / exit 1
                                                              └ ::error:: annotations
```

- `update_status_from_junit(rows, junit_path)` — parses JUnit, builds `{testcase name: PASS|FAIL}` (a `<failure>` or `<error>` child = FAIL), and writes each matched row's `status`. Rows whose `test_function` is absent from the XML are left as-is, so the uncovered gap is still caught by `uncovered_requirements`.
- `main()` — loads the matrix, applies JUnit status, prints ASIL coverage, emits `::error::Uncovered requirements: [...]` and `::error::Failing requirements: [...]` annotations, and exits non-zero via `release_gate_ok()`.

The Phase 4 functions (`load_matrix`, `uncovered_requirements`, `failing_requirements`, `asil_coverage`, `release_gate_ok`, `_is_high_asil`) are reused unchanged — the gate policy (which ASILs block) stays in the single `_is_high_asil` helper. The one design note: Phase 4's `trace_check.py` already has a `__main__` block; Phase 5 refactors it into the `main()` described here so the CLI takes both a matrix path and a JUnit path.

**Why a gap blocks a merge.** A red test says "a known behaviour broke." An uncovered ASIL C/D requirement says "we never verified a behaviour that can kill someone." The second is worse, and invisible to a normal test runner. The gate makes it a hard failure keyed to the requirement ID, so an uncovered safety requirement literally cannot be merged under branch protection.

---

## Per-Build Coverage Report (Ex22)

The report is the artifact an auditor or lead actually reads — not the raw XML. `render_markdown` reuses the Phase 4 validator so the numbers in the report and the numbers the gate acts on cannot drift apart.

```
## ADAS Requirement Coverage
**Overall:** 6/7 requirements covered (86%)

| ASIL | Covered | Total | Coverage |
|------|---------|-------|----------|
| B    | 1       | 1     | 100%     |
| B(D) | 0       | 1     | 0% ⚠️    |
| D    | 5       | 5     | 100%     |

**Uncovered:** TSR_AEB_03a
```

- Overall % = rows with both a `test_case_id` and a `test_function`, over total rows.
- Incomplete high-ASIL rows (`C`, `D`, `B(D)`) are flagged ⚠️ so the eye lands on the safety-relevant gap first.
- Published as a **sticky** PR comment (`marocchino/sticky-pull-request-comment`) so each push updates the same comment in place instead of spamming the thread, and saved as a `coverage.md` artifact for the safety case.
- A unit test (`test_coverage_report.py`) asserts the % and the ⚠️ flag on the deliberate gap, so the report generator is itself verified.

---

## The Three Tiers & Hardware Reality (Ex23)

```yaml
on:
  push: { branches: [main] }
  pull_request:
  schedule: [{ cron: "0 3 * * *" }]   # nightly 03:00 UTC
  workflow_dispatch:

jobs:
  pr-gate:            # PRs/push — matrix 3.11/3.12/3.13, fail-fast: false
                      #   pytest -m "smoke and stub" + traceability gate
  nightly-regression: # schedule only — full "stub" suite + coverage report
  bench:              # [self-hosted, hil-bench], if: false (enable when a bench exists)
```

- **`fail-fast: false`** on the matrix: one Python version failing still reports the others, so you see whether a failure is version-specific.
- **Why the split.** Cost, speed, and hardware. The real HIL bench tests need a physical ECU wired to a self-hosted runner — they cannot run on a cloud VM and they are slow. So fast software-stub smoke tests gate every PR; the full stub regression runs nightly off the critical path; the bench tests run scheduled/on-demand on the self-hosted runner. `if: false` on the `bench` job documents exactly where hardware plugs in without requiring it in the practice repo — flip it to a schedule or a `bench` label when a runner exists.

---

## Determinism & Flaky Tests

CI must be deterministic. The Phase 3 timing tests use injected synthetic timestamps specifically so CI runs do not depend on wall-clock or `sleep` — no races. If a test is still flaky, the discipline is: reproduce under the failing matrix Python version, quarantine it behind a marker so it does not block the gate while root-causing, and never paper over a *safety* test with a retry. A flaky safety test is a real finding, not a nuisance.

---

## Key Decisions

- **phase5 is the consolidated home.** Phase 3/4 sources move in and packaging makes them one importable project, killing the `sys.path`/`from src` fragility that would otherwise make CI unreliable.
- **Tiering by marker, not convention.** `stub`/`bench`/`smoke`/`regression` are declared in `pyproject.toml` and select the cloud vs hardware and fast vs full axes explicitly.
- **Status from JUnit, not by hand.** `update_status_from_junit` derives matrix status from the actual run, so the gate reflects reality per commit.
- **Reuse the Phase 4 gate unchanged.** The "which ASILs block" policy stays in `_is_high_asil`; Phase 5 only adds the CLI and JUnit mapping around it.
- **Report reuses the validator.** `coverage_report` imports from `trace_check` so the published numbers and the gate decision cannot diverge.
- **Gate uploads/comments use `if: always()`.** The audit trail must survive a failed build — that is when it matters most.
- **Bench disabled, not deleted.** `if: false` keeps the hardware tier visible and documented without requiring hardware, showing understanding of hardware tiering.
