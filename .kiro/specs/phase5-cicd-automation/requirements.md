# Requirements: Phase 5 – Automation + CI/CD Integration

## Overview

This spec covers the five exercises (19–23) that make up Phase 5 of the ADAS practice project. Phase 5 is the **capstone orchestration** phase: it introduces almost no new test logic and instead makes the artifacts built in Phases 3 and 4 run automatically, gate merges, and leave an auditable trail per commit.

The deliverables are a consolidated, installable test project (`pyproject.toml` + package layout), a tiered GitHub Actions pipeline, a CLI-extended traceability release gate that **blocks** a build, a per-build requirement coverage report surfaced on the PR, and a multi-version test matrix with scheduled regression and a conceptual self-hosted HIL bench tier.

**Working directory:** `~/Documents/adas_practice/phase5/` (consolidates phase3 + phase4)
**Python / Venv:** Python 3.13 primary, matrix also runs 3.11 and 3.12; `phase5/.venv`
**Key packages:** `pytest`, `pytest-cov`, `python-can`, `cantools`
**CI:** GitHub Actions (free for public repos)
**CLI:** `gh` (GitHub CLI), authenticated, for PR creation and watching runs
**Prerequisite:** Phase 3 complete (HIL harness emitting `results.xml`) and Phase 4 complete (traceability matrix + `trace_check.py` release gate)

The guiding principle: in a safety-critical project the pipeline does not merely "run the tests" — it **enforces the process**. A merge is blocked not only by a red test but by an *unverified safety requirement*. The suite is tiered (software-stub tests on cloud runners every PR; real-bench HIL tests on a self-hosted runner on a slower cadence), and every build leaves `results.xml` plus a coverage report keyed to requirement IDs for the safety case.

---

## Requirements

### REQ-001 – Consolidated Installable Project (Ex19)

The phase5 directory shall be the home of the consolidated suite: the Phase 3 `src/` modules (`bus_interface`, `hil_runner`, `ecu_boot`, `dtc_ecu`, `can_health`) and the Phase 4 `trace_check.py` + `trace_matrix.csv` shall live under one importable package. A `pyproject.toml` shall declare the project (`name = "adas-hil-suite"`, `requires-python = ">=3.11"`, dependencies `python-can`, `cantools`, optional `test` extra of `pytest`, `pytest-cov`) and a setuptools build backend.

After `pip install -e ".[test]"`, running `pytest` shall exercise the full suite with **no** `sys.path` hacks and no `from src...` import fragility. The phase3 and phase4 sources shall be importable as packages with no duplicated path shims.

### REQ-002 – Pytest Markers & Tiering (Ex19)

`pyproject.toml` shall declare four pytest markers under `[tool.pytest.ini_options]` so the pipeline can select tiers without "unknown marker" warnings:

- `stub` — runs against the software StubBus (cloud runner, every PR)
- `bench` — requires real HIL hardware (self-hosted runner, scheduled)
- `smoke` — fast subset for per-PR gating
- `regression` — full suite for nightly runs

The Phase 3 tests shall be tagged so that `pytest -m "smoke and stub"` selects only the fast cloud-safe subset. `pytest -m bench` on a machine with no hardware shall **skip** (not error), guarded by a fixture that checks hardware availability.

### REQ-003 – Bench-Skip Fixture (Ex19)

`conftest.py` shall provide a fixture (or hook) that detects the absence of HIL hardware and causes `bench`-marked tests to be skipped rather than errored on a cloud runner, so the same suite runs cleanly on a laptop, a cloud VM, and (conceptually) a wired bench.

### REQ-004 – Baseline GitHub Actions Pipeline (Ex20)

`.github/workflows/adas_ci.yml` shall define a workflow that triggers on `push` to `main`, all `pull_request`s, and manual `workflow_dispatch`. On each trigger it shall check out the repo, set up Python 3.13, run `pip install -e ".[test]"`, and run only the `-m "stub"` tests (bench tests excluded, not failing) producing a JUnit `results.xml` and coverage XML.

`results.xml` shall be uploaded as a build artifact with `if: always()` so a failed run still publishes its report, and test results shall surface in the PR's Checks tab (a summary via a JUnit reporter), not only in the log. The coverage XML required by Ex22 shall be produced.

### REQ-005 – Traceability Gate CLI (Ex21)

`src/trace_check.py` shall be extended with a CLI entry point usable as `python -m src.trace_check <matrix.csv> <results.xml>`. It shall:

- Add `update_status_from_junit(rows, junit_path)` that parses the JUnit XML, maps each `<testcase name>` to the matrix row whose `test_function` matches, and sets that row's status to `PASS` or `FAIL` (a `<failure>` or `<error>` child means FAIL).
- Add a `main()` that loads the matrix, updates status from JUnit, prints ASIL coverage, emits `::error::` workflow annotations naming the specific uncovered and failing requirement IDs, and exits non-zero when `release_gate_ok()` is False (exit 0 otherwise).

The existing `load_matrix`, `uncovered_requirements`, `failing_requirements`, `asil_coverage`, and `release_gate_ok` from Phase 4 shall be reused unchanged.

### REQ-006 – Traceability Gate as a Blocking CI Step (Ex21)

The workflow shall run the gate as a step after the test step: `python -m src.trace_check traceability/trace_matrix.csv results.xml`. Because the CLI exits non-zero on a gap or fail, the job shall go red and (with branch protection) the PR shall be unmergeable. The `::error::` annotations shall surface the offending requirement IDs inline on the PR.

The behaviour shall be demonstrable both ways: a PR carrying the deliberate `TSR_AEB_03a` gap goes **red**, and filling the gap turns it **green**. The README shall note the branch-protection requirement even though the practice repo is solo.

### REQ-007 – Per-Build Requirement Coverage Report (Ex22)

`src/coverage_report.py` shall provide `render_markdown(matrix_path) -> str` that reuses `load_matrix`, `asil_coverage`, and `uncovered_requirements` from `trace_check` and produces a human-readable report containing: overall requirement coverage % (covered/total), a per-ASIL covered/total/coverage table, and an explicit uncovered list. ASIL C/D (and decomposed B(D)) rows that are incomplete shall be visibly flagged (⚠️). Running it as `python -m src.coverage_report <matrix.csv>` shall print the markdown to stdout.

### REQ-008 – Coverage Report Publishing & Test (Ex22)

The workflow shall write the report to `coverage.md` (`if: always()`) and, on `pull_request` events, post it as a **sticky** PR comment that updates in place on each push rather than spamming new comments. `coverage.md` shall also be retained as a build artifact for the audit trail. A unit test (`tests/test_coverage_report.py`) shall assert that `render_markdown` reports the correct coverage % and flags the deliberate gap.

### REQ-009 – Multi-Version Matrix + Scheduled Regression + Bench Tier (Ex23)

`.github/workflows/adas_ci.yml` in its final form shall define three jobs:

- **`pr-gate`** — runs on `pull_request`/`push` across a Python matrix of `3.11`, `3.12`, `3.13` with `fail-fast: false`, executes `pytest -m "smoke and stub"`, runs the traceability gate inside the job so a coverage gap blocks merge on every PR, and uploads a per-version JUnit artifact.
- **`nightly-regression`** — runs only on a `schedule:` cron (nightly), executes the full `-m "stub"` suite (not just smoke) plus the coverage report, off the PR critical path.
- **`bench`** — targets a self-hosted runner `[self-hosted, hil-bench]`, runs `pytest -m "bench"`, is disabled by `if: false` with a comment explaining how it is enabled when a bench runner exists.

### REQ-010 – README & Tier Documentation (Ex23)

`README.md` shall document the three test tiers (PR smoke on cloud / nightly regression / bench on self-hosted hardware), explain why real HIL hardware cannot run on a cloud runner, state why a coverage *gap* — not just a red test — blocks a safety merge, and describe the branch-protection requirement on the gate. It shall document the Phase 3/4 consolidation into phase5.

### REQ-011 – Local Dry-Run Parity

Everything the cloud runner does shall be reproducible locally before pushing, via: `pip install -e ".[test]"`, then `pytest -m "smoke and stub" -v --junitxml=results.xml`, then `python -m src.trace_check traceability/trace_matrix.csv results.xml`, then `python -m src.coverage_report traceability/trace_matrix.csv`. The gate shall pass clean and fail on the deliberate gap identically to CI.

### REQ-012 – Live Verification

The cloud tiers shall be verified live: push a branch, open a PR with `gh pr create --fill`, and confirm the checks run (`gh pr checks --watch` / `gh run watch`). A clean matrix and a manually triggered run shall both be green; an injected gap shall turn the gate red. One PR shall exist end-to-end showing the full pipeline green, with the coverage comment and the audit artifacts attached.

### REQ-013 – Directory Structure

```
phase5/
├── .github/
│   └── workflows/
│       └── adas_ci.yml              # Ex20 → Ex21 → Ex23 (final form)
├── pyproject.toml                   # Ex19 — packaging + markers
├── conftest.py                      # Ex19 — bench-skip fixture
├── README.md                        # tiers + branch-protection notes
├── src/
│   ├── __init__.py
│   ├── bus_interface.py             # from phase3
│   ├── hil_runner.py                # from phase3
│   ├── ecu_boot.py                  # from phase3
│   ├── dtc_ecu.py                   # from phase3
│   ├── can_health.py                # from phase3
│   ├── trace_check.py               # phase4 + Ex21 CLI/JUnit mapping
│   └── coverage_report.py           # Ex22
├── tests/
│   ├── __init__.py
│   ├── (phase3 tests, marked stub/smoke/regression)
│   ├── test_traceability.py         # phase4
│   └── test_coverage_report.py      # Ex22
└── traceability/
    └── trace_matrix.csv             # phase4
```

---

## Acceptance Criteria Summary

| ID | Criterion |
|---|---|
| AC-001 | `pip install -e ".[test]"` then `pytest` runs the full suite with no `sys.path` hacks or `from src` fragility |
| AC-002 | Markers `stub`, `bench`, `smoke`, `regression` declared in `pyproject.toml`; no "unknown marker" warnings |
| AC-003 | `pytest -m "smoke and stub"` selects only the fast cloud-safe subset |
| AC-004 | `pytest -m bench` on a machine with no hardware skips (does not error), guarded by a fixture |
| AC-005 | Phase 3 and Phase 4 sources importable as packages; no duplicated path shims |
| AC-006 | Workflow triggers on push to main, all PRs, and manual `workflow_dispatch` |
| AC-007 | Only `-m "stub"` tests run on the cloud runner (bench excluded, not failing) |
| AC-008 | `results.xml` uploaded as an artifact with `if: always()`; results surface in the PR Checks tab |
| AC-009 | Coverage XML produced for Ex22; verified live via a pushed PR (`gh pr checks` / `gh run watch`) |
| AC-010 | `trace_check` reads `results.xml`, maps each `<testcase name>` to its row's `test_function`, updates status |
| AC-011 | CLI exits non-zero when any ASIL C/D/B(D) requirement is uncovered or any linked test failed |
| AC-012 | `::error::` annotations name the specific offending requirement IDs |
| AC-013 | Deliberate `TSR_AEB_03a` gap turns the PR red; filling it turns it green; branch-protection noted in README |
| AC-014 | Coverage report shows overall %, per-ASIL table, and explicit uncovered list; incomplete C/D rows flagged ⚠️ |
| AC-015 | Report posted as a sticky PR comment and saved as `coverage.md` artifact |
| AC-016 | A unit test asserts `render_markdown` reports the right % and flags the gap |
| AC-017 | PR gate runs `smoke and stub` across a 3-version Python matrix with `fail-fast: false` |
| AC-018 | Traceability gate runs inside the PR gate so a gap blocks merge on every PR |
| AC-019 | Nightly `schedule:` job runs the full stub suite + coverage report, off the PR critical path |
| AC-020 | `bench` job present, gated to `[self-hosted, hil-bench]`, disabled by `if: false`, with an enable comment |
| AC-021 | README documents the three tiers and the branch-protection requirement; explains why HIL can't run on cloud |
| AC-022 | Cloud tiers verified live: PR gate + manual run both green on a clean matrix, red on an injected gap |
