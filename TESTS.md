
# ARGIR Test Suite (0.3.x)

This suite gives you **natural-language** test cases and (optionally) **golden fixtures** so you can test ARGIR deterministically, without depending on LLM variability.

## Contents
- `tests/nl/*.txt` — plain English inputs
- `tests/fixtures/*.json` — canonical LLM JSON drafts for deterministic runs
- `tests/harness.py` — helper to run a case via `argir.pipeline.run_pipeline`
- `tests/test_suite.py` — `unittest` tests (work with or without fixtures)
- `run_tests.py` — convenience CLI wrapper

## Two ways to run

### A) Deterministic (fixtures only – no LLM)
Best for CI and regression.
```bash
python run_tests.py --fixtures
# or:
ARGIR_TEST_MODE=fixtures python -m unittest tests/test_suite.py -v
```

### B) LLM mode (from natural language)
Runs the parser through the real LLM. Assertions are **property-based** (fewer false failures), but still check key invariants.
```bash
# Make sure ARGIR can call Gemini/Vertex (set either):
export GEMINI_API_KEY=...
#   or
export GOOGLE_CLOUD_PROJECT=... ; export GOOGLE_CLOUD_LOCATION=us-central1
# Run:
python run_tests.py --llm
# or simply:
python -m unittest tests/test_suite.py -v
```

> Tip: confirm you’re loading the right ARGIR build:
```bash
python -m argir.cli -V
```

## What the tests cover

1. **Modus ponens + undercut** (`mp_with_undercut`)
   - Canonical atoms present, no derivability gaps, rule axiom + linkage emitted, and a goal for the main conclusion.

2. **Negation flow** (`negation_fact`)
   - TPTP contains negated atoms `~(pred)` as expected.

3. **Defeasible rule lowering** (`defeasible_rule`)
   - Classical FOL vs `--defeasible-fol` — checks `~(exception)` appears in antecedents only in defeasible mode.

4. **Multiple conclusions** (`multi_conclusions`)
   - No auto-goal when there are two unreferenced inference conclusions; override with `goal_id` or `--goal`.

5. **Support cycle detection** (`support_cycle`)
   - Finds a support cycle.

6. **Mutual rebuttal** (`mutual_attack`)
   - APX shows `att(A,notA)` and `att(notA,A)`.

7. **Strict lexicon enforcement (missing)** (`lexicon_missing`)
   - Raises due to missing `metadata.atom_lexicon`.

8. **Strict lexicon enforcement (mismatch)** (`lexicon_mismatch`)
   - Raises when an atom name isn’t a key in the lexicon.

## Programmatic usage

You can import the harness and run cases from your own tests:
```python
from tests.harness import run_case
res = run_case("mp_with_undercut", use_fixture=True, fol_mode="classical")
print(res["fof"])  # list of TPTP lines
```

## Notes
- E‑prover assertions are kept soft; we check for key axioms/goals rather than exact proof statuses (which depend on `eprover` availability). If `eprover` is installed, you’ll get actual summaries in `res["fol_summary"]`.
- If you want stricter LLM-mode tests, tighten the parser prompt or add more **invariant assertions** (e.g., “every atom pred must appear in `metadata.atom_lexicon`”). This suite already enforces that via the canonicalizer.
