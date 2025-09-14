# ARGIR — Unified Argument IR

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/namin/argir)

> A clean, strict, and analyzable pipeline from **natural language → argument graph → AF semantics → FOL (TPTP)**.

See also [Argument Debugger](https://github.com/namin/argument-debugger), an LLM+ASP system for analyzing and repairing arguments.

This README covers setup, CLI usage, LLM configuration, generated outputs, testing, and the core IR contract.

---

## 1) Install / Setup

You can run the package straight from source (no build needed).

```bash
# Core dependencies (Python 3.9+)
pip install "pydantic>=2.0" google-genai clingo joblib

# System dependencies (optional):
# - eprover: FOL theorem prover (install via package manager, e.g., apt/brew)

# Note on dependencies:
# - clingo: ASP solver for computing argumentation framework semantics
# - joblib: Caching library for LLM responses (reduces API calls and costs)
```

---

## 2) Configure the LLM

ARGIR uses **google-genai**. Choose **one** of the following:

- **Gemini API key**:
  ```bash
  export GEMINI_API_KEY=your_key_here
  ```

- **Vertex AI** (Project + Location, uses your gcloud auth):
  ```bash
  export GOOGLE_CLOUD_PROJECT=your-project-id
  export GOOGLE_CLOUD_LOCATION=us-central1  # or your region
  ```

Optional environment variables:
- `LLM_MODEL` (default: `gemini-2.5-flash`)
- `CACHE_LLM` (set to any value to enable joblib caching)
- `LLM_CACHE_DIR` (default: `.cache/llm`)

---

## 3) Quickstart (CLI)

From the project folder (where `argir/` lives):

```bash
# Check you’re running the right package version and path
python -m argir.cli -V
# → ARGIR v0.3.3 @ /path/to/argir/__init__.py

# Run on the sample
python -m argir.cli examples/sample.txt --out out

# Optional: defeasible FOL (exceptions become negated conditions in antecedent)
python -m argir.cli examples/sample.txt --out out --defeasible-fol

# Optional: choose a specific goal to prove in FOL (by node id)
# First run without --goal to see node IDs in report.md, then use one like:
python -m argir.cli examples/sample.txt --out out --goal C1

# Optional: use soft IR extraction with deterministic canonicalization
# This is more robust than the default strict one-shot extraction
python -m argir.cli examples/sample.txt --out out --soft

# Optional: try multiple samples with soft extraction (picks best)
python -m argir.cli examples/sample.txt --out out --soft --k-samples 3
```

**CLI Options**:
- `--defeasible-fol` — Export FOL with exceptions as negated conditions
- `--goal NODE_ID` — Force specific node as FOL conjecture
- `--soft` — Use two-stage soft IR extraction (more robust)
- `--k-samples N` — Try N soft IR samples, pick best (default: 1, only with --soft)
- `--strict-fail` — Exit with error on validation issues (for CI/CD)

**Outputs written to `--out`**:
- `report.md` — human‑readable report (nodes, edges, findings, AF semantics, FOL)
- `argir.json` — canonical ARGIR object (strictly validated)
- `fof.p` — TPTP FOF axioms + (optional) conjecture
- `draft.json` — raw LLM JSON (for debugging)
- `fol_summary.json` — E‑prover summary (if `eprover` is installed)

The **AF Semantics** section in `report.md` shows accepted arguments under different semantics (grounded, preferred, stable) computed via clingo

---

## 4) Web Frontend

For a simpler, see `WEB_README.md`

---

## 5) Tests

Run `python tests/run.py --soft`. Do export `CACHE_LLM=true`.

---

## 6) Programmatic Usage

```python
from argir.pipeline import run_pipeline, run_pipeline_soft

text = "If it rains, the streets get wet. It is raining. So, the streets will get wet."

# Standard strict pipeline (one-shot extraction)
res = run_pipeline(text, fol_mode="classical", goal_id=None)

# Soft pipeline (two-stage: soft IR → canonicalization → strict ARGIR)
res = run_pipeline_soft(text, fol_mode="classical", goal_id=None, k_samples=3)

print(res["report_md"])   # markdown report
print(res["fof"])         # list of TPTP lines
print(res["argir"])       # canonical JSON-safe dict of the ARGIR
```

- `fol_mode`: `"classical"` or `"defeasible"`
- `goal_id`: force the FOL conjecture to a specific node id
- `k_samples`: (soft pipeline only) number of extraction attempts, picks best

**Auto‑goal selection**: if there is exactly one **inference node** (has premises + conclusion) that isn't referenced by others, ARGIR emits `fof(goal, conjecture, …)` automatically. Otherwise, use `--goal`.

---

## 7) Soft Pipeline (Recommended)

The **soft pipeline** (`--soft` flag) is a more robust two-stage approach that addresses the brittleness of one-shot ARGIR generation:

**Stage 1: Soft Extraction (LLM)**
- LLM produces a permissive "Soft IR" format
- No canonical predicates required
- Simple predicate names allowed (e.g., "raining", "streets_wet")
- Flexible node IDs and references

**Stage 2: Canonicalization & Compilation (Deterministic)**
- Automatically normalizes predicates (lowercase, underscores, strip articles)
- Builds `atom_lexicon` from usage
- Assigns stable node IDs (R1, C1, P1)
- Validates and auto-repairs common issues
- Produces strict ARGIR satisfying all contracts

**Benefits**:
- **Higher success rate** — LLM focuses on semantics, not syntax
- **Deterministic canonicalization** — Consistent predicates across runs
- **Best-of-k selection** — Try multiple samples, pick the one with fewest errors
- **Graceful error handling** — Auto-repairs missing lexicon entries, dangling refs

**When to use**:
- Complex arguments with many predicates
- When the standard pipeline fails with lexicon errors
- Production systems requiring robustness
- Experimenting with different LLM models

---

## 8) The ARGIR Contract (Strict Mode)

ARGIR is strict on atoms to make FOL sound and comparable.

- The LLM **must** return a single JSON object with keys:
  - `version`, `source_text`
  - `graph: { nodes: InferenceStep[], edges: Edge[] }`
  - `metadata.atom_lexicon`: **required** canonical predicates (keys) → example surface forms (values)

- **Canonical atom enforcement**:
  - Every `atoms[].pred` in nodes/rules **must** be a key in `metadata.atom_lexicon` (or legacy alias `metadata.symbols.predicates`).
  - If missing or mismatched, the pipeline **errors** (no fallback).

- **Structure**:
  - Node = `{ id, premises[], rule?, conclusion?, span?, rationale? }`
  - Premise = `Statement` or `Ref` (`{"kind":"Ref","ref": "nodeId"}`)
  - Rule = `{ name, strict, antecedents[], consequents[], exceptions[], ... }`
  - Edge = `{ source, target, kind: "support"|"attack", attack_kind?, rationale? }`

- **Reference‑aware coherence**:
  - If a node’s premises include a `Ref` to a rule node, it’s treated as *rule‑backed* — no false “missing rule” finding.

---

## 9) AF & FOL

- **AF projection**: every node is an argument; attack edges become `att(a,b)`; support is not encoded in APX (kept in the graph for coherence checks).

- **AF Semantics computation**: ARGIR uses **clingo** (Answer Set Programming solver) to compute standard Dung semantics:
  - **Grounded**: the minimal complete extension
  - **Preferred**: maximal admissible sets
  - **Stable**: extensions that attack all outside arguments
  - Results appear in `report.md` under "AF Semantics" section with accepted arguments

- **FOL lowering** (TPTP FOF):
  - Always emits:
    - **Rule axioms** for rule nodes (antecedents ⇒ consequents).
    - **Premise‑only facts** and **conclusion‑only facts**.
    - **Linkage axioms** for inference nodes: `(premises ⇒ conclusion)` where `Ref` to a rule collapses into that rule’s formula.
  - **Defeasible mode** (`--defeasible-fol`): every exception in a rule becomes a **negated** condition conjoined to antecedents.

- **Goal selection**:
  - If exactly one inference node is unreferenced → auto `fof(goal, conjecture, …)`.
  - Otherwise, supply `--goal NODE_ID` to force a conjecture.
  - To find node IDs: run once without `--goal`, check `report.md` for node IDs (e.g., C1, R1, P1)
  - The auto-selected goal (if any) appears in `metadata.goal_candidate_id` in `argir.json`

---

## 10) Troubleshooting

- **`LLMNotConfigured`**  
  Set either `GEMINI_API_KEY` or `GOOGLE_CLOUD_PROJECT` (+ `GOOGLE_CLOUD_LOCATION`).

- **`metadata.atom_lexicon ... missing or empty`**  
  The LLM must include canonical predicates. Tighten the prompt or run in fixtures mode to debug.

- **`Atom predicates must be canonical ...`**  
  An `atoms[].pred` is not a key in the lexicon. Normalize or update the lexicon.

- **No `fof(goal, ...)` emitted**  
  Multiple candidate conclusions. Use `--goal NODE_ID`.

- **E‑prover "not found"**
  Install eprover (optional). The rest of the pipeline still works.

- **Version/path confusion**
  Use `python -m argir.cli -V` to see the active package path and version.

