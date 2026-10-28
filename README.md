# Phase 5 — Automation + CI/CD Integration

ADAS Software Test Engineer practice. Phase 5 is the **capstone orchestration**
phase: it adds almost no new test logic and instead makes the artifacts built
in Phases 3 and 4 run automatically, gate merges, and leave an auditable trail
per commit. The pipeline is the deliverable.

In a safety-critical project the pipeline does not merely "run the tests" — it
**enforces the process**. A merge is blocked not only by a red test but by an
*unverified safety requirement*.

## Consolidation

Phase 5 is the single home of the consolidated suite. The Phase 3 HIL harness
and the Phase 4 traceability gate were copied in here and made one installable
package, so `pip install -e .` puts `src` on the path with no `sys.path` hacks
or `from src` import fragility. (Phases 3 and 4 remain intact in their own
folders; this is a copy, so a fix made there must be ported here by hand.)

```
phase5/
├── .github/workflows/adas_ci.yml   # tiered pipeline (Ex20 -> Ex23)
├── pyproject.toml                  # packaging + pytest markers (Ex19)
├── conftest.py                     # bench-skip fixture (Ex19)
├── src/
│   ├── bus_interface.py  hil_runner.py  ecu_boot.py  dtc_ecu.py  can_health.py  (from phase3)
│   ├── trace_check.py              # phase4 validator + Ex21 JUnit/CLI gate
│   └── coverage_report.py          # per-build coverage report (Ex22)
├── tests/
│   ├── test_boot_sequence.py  test_bus_recovery.py  test_capstone_scenario.py
│   ├── test_dtc.py  test_hil_runner.py            (from phase3, now marked)
│   ├── test_traceability.py                       (from phase4)
│   ├── test_coverage_report.py                    # Ex22
│   └── test_bench_tier.py                         # bench tier (skips w/o hardware)
└── traceability/trace_matrix.csv                  # from phase4 (with a deliberate gap)
```

## The three test tiers

Tiering is enforced by pytest markers (declared in `pyproject.toml`), not by
convention. Two axes: software-stub vs real-hardware, and fast-subset vs
full-suite.

| Tier | Selector | Where it runs | Cadence | CI job |
|---|---|---|---|---|
| PR smoke | `-m "smoke and stub"` | cloud runner (`ubuntu-latest`) | every PR / push | `pr-gate` |
| Nightly regression | `-m "stub"` (full) | cloud runner | nightly (cron) | `nightly-regression` |
| HIL bench | `-m "bench"` | self-hosted, wired to an ECU | scheduled / on-demand | `bench` (disabled here) |

**Why not run everything on every PR?** Cost, speed, and hardware. The fast
`smoke and stub` subset gates every PR across a Python-version matrix. The full
stub regression is heavier, so it runs nightly off the critical path. The HIL
bench tests need a physical ECU wired to a self-hosted runner — they **cannot
run on a cloud VM** and they are slow, so they run on a slower cadence on the
bench machine.

**Why the bench tier can't run on a cloud runner.** A GitHub-hosted runner is a
disposable cloud VM with no physical CAN interface and no ECU attached. The HIL
tests inject stimulus onto a real bus and read a real ECU's response — there is
nothing on a cloud VM to talk to. So the `bench` job targets a **self-hosted**
runner (`runs-on: [self-hosted, hil-bench]`) physically connected to the
hardware. In this practice repo the `bench` job is disabled with `if: false`
because no such runner exists; the job is kept visible to document exactly where
hardware plugs in. See the comment block above the `bench` job for how to enable
it.

The payoff of the injectable `BusInterface` from Phase 3: `bench` tests use a
real `python-can` backend while `stub` tests use `StubBus` — identical test
sequences, different bus.

## The traceability gate (why a gap blocks a merge)

After tests run, `src/trace_check.py` parses the JUnit `results.xml`, maps each
`<testcase>` back to its row in `traceability/trace_matrix.csv`, updates status,
and runs the release gate. The gate **exits non-zero — failing the job** — if
any ASIL C / D (or decomposed B(D)) requirement is uncovered **or** any linked
test failed.

A red test says "a known behaviour broke." An uncovered ASIL C/D requirement
says "we never verified a behaviour that can cause harm" — worse, and invisible
to a normal test runner. The gate makes the second a hard failure keyed to the
requirement ID, so an uncovered safety requirement cannot slip through.

The matrix ships a **deliberate gap** (`TSR_AEB_03a`, an ASIL B(D) requirement
with no test). With that gap present the gate is red; filling the row (a test
case + a passing test function) turns it green. This proves the gate has teeth.

### Branch protection

For the gate to actually block a merge, enable branch protection on `main` and
require the `pr-gate` check to pass:

> Settings → Branches → Add rule for `main` → *Require status checks to pass
> before merging* → select the `pr-gate` checks.

With that on, a PR with an uncovered ASIL C/D/B(D) requirement — or any failing
linked test — **cannot be merged**, and the `::error::` annotations name the
offending requirement IDs inline on the PR. (This practice repo is solo, but the
requirement is noted so the enforcement is explicit.)

## Auditable artifacts

Every build leaves, regardless of gate outcome (`if: always()`):

- `results.xml` — JUnit results, per Python version (`junit-3.11/3.12/3.13`).
- `coverage.md` — requirement coverage report (overall %, per-ASIL table,
  uncovered list), posted as a **sticky PR comment** and retained as an
  artifact for the safety case.

## Setup & local verification

Everything the cloud runner does can be dry-run locally first:

```bash
cd ~/Documents/adas_practice/phase5
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"

# 1. the exact PR-gate test command
pytest -m "smoke and stub" -v --junitxml=results.xml

# 2. the blocking gate — exits 0 clean, exit 1 on the deliberate gap
python -m src.trace_check traceability/trace_matrix.csv results.xml

# 3. the coverage report
python -m src.coverage_report traceability/trace_matrix.csv
```

The `bench` tier skips cleanly without hardware:

```bash
pytest -m bench        # 1 skipped (set HIL_BENCH=1 on a real bench to run it)
```

## Push and watch the live pipeline

```bash
git checkout -b ci/pipeline
git add -A && git commit -m "Phase 5: CI/CD pipeline with traceability gate"
git push -u origin ci/pipeline
gh pr create --fill
gh pr checks --watch        # or: gh run watch
```

With the deliberate gap in place the `pr-gate` check goes **red** and the
coverage comment shows `TSR_AEB_03a` uncovered. Fill the matrix row to see it go
**green**.
