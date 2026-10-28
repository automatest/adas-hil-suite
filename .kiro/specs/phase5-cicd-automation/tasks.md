# Tasks: Phase 5 – Automation + CI/CD Integration

## Task List

- [ ] 1. Set up phase5 repo, environment, and consolidate Phase 3/4 sources
- [ ] 2. Exercise 19 — Package the suite as one installable project
- [ ] 3. Exercise 20 — GitHub Actions: run tests + publish JUnit
- [ ] 4. Exercise 21 — Traceability gate as a blocking CI step
- [ ] 5. Exercise 22 — Per-build requirement coverage report
- [ ] 6. Exercise 23 (capstone) — Matrix + scheduled regression + bench tier
- [ ] 7. Verify locally, then live on GitHub, and complete the checklist

---

- [ ] Task 1 – Set up phase5 repo, environment, and consolidate Phase 3/4 sources

Make `phase5/` the home of the consolidated suite. Create the git repo and venv, then move the Phase 3 `src/` modules and the Phase 4 `trace_check.py` + `trace_matrix.csv` in so they form one project.

### Subtasks

- [ ] 1.1 `git init` in `phase5/`; create `phase5/.venv` (Python 3.13) and activate it
- [ ] 1.2 Create the `src/`, `tests/`, `traceability/`, `.github/workflows/` directories
- [ ] 1.3 Move phase3 `src/` modules (`bus_interface`, `hil_runner`, `ecu_boot`, `dtc_ecu`, `can_health`) + `src/__init__.py` into `phase5/src/`
- [ ] 1.4 Move phase3 tests into `phase5/tests/` and `tests/__init__.py`
- [ ] 1.5 Move phase4 `trace_check.py` into `phase5/src/` and `trace_matrix.csv` into `phase5/traceability/`
- [ ] 1.6 Move phase4 `tests/test_traceability.py` into `phase5/tests/`
- [ ] 1.7 `pip install pytest pytest-cov python-can cantools`

### Acceptance Criteria

- Consolidated layout matches REQ-013; phase3/phase4 sources live under one `src/` package
- `phase5/.venv` has pytest, pytest-cov, python-can, cantools installed

### Files

- repo skeleton: `src/`, `tests/`, `traceability/`, `.github/workflows/`

---

- [ ] Task 2 – Exercise 19: Package the suite as one installable project

### Subtasks

- [ ] 2.1 Write `pyproject.toml` (`name = "adas-hil-suite"`, `requires-python = ">=3.11"`, deps `python-can`/`cantools`, `test` extra, setuptools backend)
- [ ] 2.2 Declare the four markers (`stub`, `bench`, `smoke`, `regression`) under `[tool.pytest.ini_options]` with `testpaths` and `addopts = "-ra"`
- [ ] 2.3 Remove the `sys.path` / root-`conftest` shims from Phases 3/4; rely on the installed package
- [ ] 2.4 Tag Phase 3 tests with `stub`/`smoke`/`regression` markers; tag any real-ECU test `bench`/`regression`
- [ ] 2.5 Write `conftest.py` with a bench-skip fixture that skips `bench` tests when no hardware is present
- [ ] 2.6 `pip install -e ".[test]"`, then `pytest` runs the full suite with no path hacks
- [ ] 2.7 Confirm `pytest -m "smoke and stub"` selects the fast subset and `pytest -m bench` skips (does not error)

### Acceptance Criteria

- AC-001, AC-002, AC-003, AC-004, AC-005 satisfied (see requirements.md)

### Files

- `pyproject.toml`, `conftest.py`, `src/__init__.py`, marked `tests/*`

---

- [ ] Task 3 – Exercise 20: GitHub Actions — run tests + publish JUnit

### Subtasks

- [ ] 3.1 Create `.github/workflows/adas_ci.yml` triggering on `push` (main), `pull_request`, `workflow_dispatch`
- [ ] 3.2 Steps: `actions/checkout@v4`, `actions/setup-python@v5` (3.13), `pip install -e ".[test]"`
- [ ] 3.3 Run `pytest -m "stub" -v --junitxml=results.xml --cov=src --cov-report=xml`
- [ ] 3.4 Upload `results.xml` via `actions/upload-artifact@v4` with `if: always()`
- [ ] 3.5 Add a `dorny/test-reporter@v1` step (`if: always()`) to surface the JUnit summary in the Checks tab

### Acceptance Criteria

- AC-006, AC-007, AC-008, AC-009 satisfied

### Files

- `.github/workflows/adas_ci.yml`

---

- [ ] Task 4 – Exercise 21: Traceability gate as a blocking CI step

### Subtasks

- [ ] 4.1 Add `update_status_from_junit(rows, junit_path)` to `src/trace_check.py` (map `<testcase name>` → row `test_function`, set PASS/FAIL)
- [ ] 4.2 Refactor the existing `__main__` block into a `main()` taking `<matrix.csv> <results.xml>` args
- [ ] 4.3 `main()` prints ASIL coverage, emits `::error::` annotations for uncovered + failing requirement IDs
- [ ] 4.4 `main()` exits non-zero when `release_gate_ok()` is False, 0 otherwise; reuse Phase 4 functions unchanged
- [ ] 4.5 Add the gate step to the workflow: `python -m src.trace_check traceability/trace_matrix.csv results.xml`
- [ ] 4.6 Demonstrate red on the deliberate `TSR_AEB_03a` gap; green when the gap is filled
- [ ] 4.7 Note the branch-protection requirement in the README

### Acceptance Criteria

- AC-010, AC-011, AC-012, AC-013 satisfied

### Files

- `src/trace_check.py`, `.github/workflows/adas_ci.yml`, `README.md`

---

- [ ] Task 5 – Exercise 22: Per-build requirement coverage report

### Subtasks

- [ ] 5.1 Create `src/coverage_report.py` with `render_markdown(matrix_path)` reusing `load_matrix`/`asil_coverage`/`uncovered_requirements`
- [ ] 5.2 Report shows overall %, per-ASIL covered/total/coverage table, and explicit uncovered list
- [ ] 5.3 Flag incomplete ASIL C/D/B(D) rows with ⚠️
- [ ] 5.4 Make it runnable as `python -m src.coverage_report <matrix.csv>` (prints markdown)
- [ ] 5.5 Add a workflow step writing `coverage.md` (`if: always()`)
- [ ] 5.6 Add a sticky PR-comment step (`marocchino/sticky-pull-request-comment@v2`) gated to `pull_request`
- [ ] 5.7 Retain `coverage.md` as a build artifact
- [ ] 5.8 Write `tests/test_coverage_report.py` asserting the % and the gap ⚠️ flag

### Acceptance Criteria

- AC-014, AC-015, AC-016 satisfied

### Files

- `src/coverage_report.py`, `tests/test_coverage_report.py`, `.github/workflows/adas_ci.yml`

---

- [ ] Task 6 – Exercise 23 (capstone): Matrix + scheduled regression + bench tier

### Subtasks

- [ ] 6.1 Add a `schedule:` cron (`0 3 * * *`) trigger to the workflow
- [ ] 6.2 `pr-gate` job: matrix `3.11`/`3.12`/`3.13`, `fail-fast: false`, `pytest -m "smoke and stub"` + gate, per-version JUnit artifact
- [ ] 6.3 `nightly-regression` job: `if: github.event_name == 'schedule'`, full `-m "stub"` suite + coverage report
- [ ] 6.4 `bench` job: `runs-on: [self-hosted, hil-bench]`, `pytest -m "bench"`, `if: false` with an enable comment
- [ ] 6.5 Route each trigger to the right job via `if:` conditions
- [ ] 6.6 Document the three tiers + branch-protection + why HIL can't run on cloud in `README.md`

### Acceptance Criteria

- AC-017, AC-018, AC-019, AC-020, AC-021 satisfied

### Files

- `.github/workflows/adas_ci.yml`, `README.md`

---

- [ ] Task 7 – Verify locally, then live on GitHub, and complete the checklist

### Subtasks

- [ ] 7.1 Local dry-run: `pip install -e ".[test]"`; `pytest -m "smoke and stub" -v --junitxml=results.xml`
- [ ] 7.2 Local gate passes clean: `python -m src.trace_check traceability/trace_matrix.csv results.xml`
- [ ] 7.3 Local report: `python -m src.coverage_report traceability/trace_matrix.csv`
- [ ] 7.4 Confirm the gate fails locally on the deliberate `TSR_AEB_03a` gap and passes when filled
- [ ] 7.5 `git checkout -b ci/pipeline`, commit, `git push -u origin ci/pipeline`, `gh pr create --fill`
- [ ] 7.6 `gh pr checks --watch` (or `gh run watch`): confirm matrix green, gate green, sticky coverage comment posted
- [ ] 7.7 Inject a gap on a branch to confirm the PR gate goes red, then revert
- [ ] 7.8 Confirm `results.xml` + `coverage.md` artifacts attached; complete the Phase 5 checklist

### Acceptance Criteria

- AC-022 satisfied; REQ-011 and REQ-012 verified; Phase 5 completion checklist fully checked

### Files

- verification only (no new sources)
