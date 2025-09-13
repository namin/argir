# ARGIR — Unified Argument IR

> A clean, strict, and analyzable pipeline from **natural language → argument graph → AF semantics → FOL (TPTP)**.

See also [Argument Debugger](https://github.com/namin/argument-debugger), an LLM+ASP system for analyzing and repairing arguments.

This README covers setup, CLI usage, LLM configuration, generated outputs, testing, and the core IR contract.

---

## 1) Install / Setup

You can run the package straight from source (no build needed).

```bash
# Dependencies (Python 3.9+)
pip install "pydantic>=2.0" google-genai
# Optional: joblib (for prompt/response caching), eprover (for proof search)
pip install joblib
# eprover is a native binary; install it via your package manager if you want proofs
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
python -m argir.cli examples/sample.txt --out out --goal conclusion_1
```

**Outputs written to `--out`**:
- `report.md` — human‑readable report (nodes, edges, findings, AF, FOL)
- `argir.json` — canonical ARGIR object (strictly validated)
- `fof.p` — TPTP FOF axioms + (optional) conjecture
- `draft.json` — raw LLM JSON (for debugging)
- `fol_summary.json` — E‑prover summary (if `eprover` is installed)

---

## 4) Web Frontend

For a simpler, graphical interface:

```bash
# Install dependencies (if not already installed)
pip install flask gunicorn

# Development server
python web.py

# Production server (recommended for deployment)
python web.py --production

# Open browser to: http://127.0.0.1:5000
```

The web frontend provides:
- Clean, mobile-responsive interface
- All CLI functionality (defeasible FOL, goal selection)
- Rich results display with collapsible sections
- API endpoint for programmatic access
- Built-in examples to get started

See `WEB.md` for detailed usage instructions.

---

## 5) Programmatic Usage

```python
from argir.pipeline import run_pipeline

text = "If it rains, the streets get wet. It is raining. So, the streets will get wet."
res = run_pipeline(text, fol_mode="classical", goal_id=None)

print(res["report_md"])   # markdown report
print(res["fof"])         # list of TPTP lines
print(res["argir"])       # canonical JSON-safe dict of the ARGIR
```

- `fol_mode`: `"classical"` or `"defeasible"`
- `goal_id`: force the FOL conjecture to a specific node id

**Auto‑goal selection**: if there is exactly one **inference node** (has premises + conclusion) that isn’t referenced by others, ARGIR emits `fof(goal, conjecture, …)` automatically. Otherwise, use `--goal`.

---

## 6) The ARGIR Contract (What the LLM must produce)

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

## 7) AF & FOL

- **AF projection**: every node is an argument; attack edges become `att(a,b)`; support is not encoded in APX (kept in the graph for coherence checks).

- **FOL lowering** (TPTP FOF):
  - Always emits:
    - **Rule axioms** for rule nodes (antecedents ⇒ consequents).
    - **Premise‑only facts** and **conclusion‑only facts**.
    - **Linkage axioms** for inference nodes: `(premises ⇒ conclusion)` where `Ref` to a rule collapses into that rule’s formula.
  - **Defeasible mode** (`--defeasible-fol`): every exception in a rule becomes a **negated** condition conjoined to antecedents.

- **Goal selection**:
  - If exactly one inference node is unreferenced → auto `fof(goal, conjecture, …)`.
  - Otherwise, supply `--goal NODE_ID` to force a conjecture.

---

## 8) Testing

A separate test suite (natural‑language + fixtures) is available.

**Deterministic (fixtures only):**

```bash
# Run with fixtures (no LLM calls)
ARGIR_TEST_MODE=fixtures python -m unittest tests/test_suite.py -v
# or use the provided run_tests.py in the suite repo
```

**LLM mode:**

```bash
python -m unittest tests/test_suite.py -v
```

The suite checks: canonical atoms, reference‑aware coherence, defeasible lowering, APX, cycles, and strict lexicon errors.

---

## 9) Troubleshooting

- **`LLMNotConfigured`**  
  Set either `GEMINI_API_KEY` or `GOOGLE_CLOUD_PROJECT` (+ `GOOGLE_CLOUD_LOCATION`).

- **`metadata.atom_lexicon ... missing or empty`**  
  The LLM must include canonical predicates. Tighten the prompt or run in fixtures mode to debug.

- **`Atom predicates must be canonical ...`**  
  An `atoms[].pred` is not a key in the lexicon. Normalize or update the lexicon.

- **No `fof(goal, ...)` emitted**  
  Multiple candidate conclusions. Use `--goal NODE_ID`.

- **E‑prover “not found”**  
  Install eprover (optional). The rest of the pipeline still works.

- **Version/path confusion**  
  Use `python -m argir.cli -V` to see the active package path and version.

