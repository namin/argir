# ARGIR Codebase Explanation

## Overview

**ARGIR** (Argument Graph Intermediate Representation) is a system that transforms natural language arguments into formal representations that can be analyzed using:
- **Argumentation Framework (AF)** semantics via Answer Set Programming (Clingo)
- **First-Order Logic (FOL)** via automated theorem proving (E-prover)

The system can detect logical issues and automatically generate repairs to fix them.

---

## Core Architecture

### 1. **Data Model** (`argir/core/model.py`)

The foundation is a **strongly-typed Pydantic model** with these key components:

**Atoms & Statements:**
- `Atom`: A logical predicate with arguments (e.g., `raining(paris)`)
  - `pred`: predicate name (canonical)
  - `args`: list of `Term` objects (Var or Const)
  - `negated`: boolean for negation

- `Statement`: Natural language text + logical atoms
  - `text`: source text
  - `atoms`: list of Atom objects
  - `quantifiers`: forall/exists quantifiers
  - `span`: text location in source

**Rules:**
- `Rule`: Formal inference rule
  - `antecedents`: premises (if conditions)
  - `consequents`: conclusions (then conditions)
  - `exceptions`: defeasible exceptions (unless conditions)
  - `strict`: boolean (strict vs defeasible)
  - `scheme`: argumentation scheme type

**Graph Structure:**
- `InferenceStep` (Node): Represents an argument step
  - `id`: unique identifier (C1, R1, P1)
  - `premises`: list of Statements or NodeRefs
  - `rule`: optional Rule
  - `conclusion`: optional Statement

- `Edge`: Connections between nodes
  - `source`, `target`: node IDs
  - `kind`: "support" or "attack"
  - `attack_kind`: rebut/undermine/undercut

**ARGIR:**
- Top-level container
  - `graph`: ArgumentGraph (nodes + edges)
  - `metadata`: atom_lexicon, goal_id, etc.

---

### 2. **Pipeline Modes**

ARGIR supports two extraction modes:

#### **Strict Pipeline** (`run_pipeline`)
- **One-shot extraction**: LLM directly produces canonical ARGIR
- **Strict validation**: All predicates must be in `atom_lexicon`
- **Fast but brittle**: Works well for simple arguments

#### **Soft Pipeline** (`run_pipeline_soft`) — **Recommended**
Two-stage process:

**Stage 1: Soft Extraction** (LLM)
- LLM produces permissive "Soft IR" format
- No canonical predicates required
- Simple predicate names allowed (e.g., "raining", "streets_wet")
- Flexible node IDs and references

**Stage 2: Compilation** (`compile_soft.py`)
- **Canonicalization**: Normalizes predicates (lowercase, underscores)
- **ID assignment**: Assigns stable IDs (R1=rule, C1=conclusion, P1=premise)
- **Implicit rule synthesis**: Creates rules for nodes with premises+conclusion but no rule
- **Auto-edge generation**: Creates support edges from node references
- **Validation & repair**: Fixes common issues automatically

**Benefits:**
- Higher success rate
- Best-of-k selection (try k samples, pick best)
- Graceful error handling

---

### 3. **Key Subsystems**

#### **A. Natural Language Processing** (`argir/nlp/`)

**`llm.py`**: LLM interface
- Supports Gemini API (via google-genai)
- Caching with joblib (set `CACHE_LLM=true`)
- Request-scoped API keys

**`parse.py`**: Extraction prompts
- Structured prompts for LLM
- JSON schema guidance

#### **B. Canonicalization** (`argir/canonicalize.py`, `compile_soft.py`)

**AtomTable**: Manages canonical predicates
- Tracks predicates → arity mapping
- Tracks surface forms (aliases)
- Lemmatization with spaCy
- Entity extraction for arguments

**Variable Detection**:
- Only recognizes specific patterns: `X`, `Y`, `Z`, `W`, `U`, `V` (with optional digits)
- Avoids treating proper nouns as variables

#### **C. Validation & Checks** (`argir/checks/`, `argir/validate.py`)

**Structural checks:**
- Missing or dangling node references
- Lexicon completeness
- Atom canonicality
- Graph coherence

**Auto-repairs:**
- `patch_missing_lexicon`: Adds missing predicates to lexicon
- Reference resolution

#### **D. Argumentation Framework Semantics** (`argir/semantics/`)

**AF Projection:**
- Each node → AF argument
- Attack edges → `att(a,b)` facts
- Support edges kept for coherence (not in AF semantics)

**Clingo Backend** (`af_clingo.py`):
- Computes standard Dung semantics:
  - **Grounded**: minimal complete extension
  - **Preferred**: maximal admissible sets
  - **Stable**: extensions attacking all outside arguments
- Uses Answer Set Programming via Python clingo library

#### **E. FOL Translation** (`argir/fol/`)

**`translate.py`**: ARGIR → FOL (TPTP format)
- **Rule axioms**: `antecedents => consequents`
- **Premise facts**: standalone premises
- **Conclusion facts**: standalone conclusions
- **Linkage axioms**: `premises => conclusion` for inference nodes
- **Defeasible mode**: exceptions become negated conditions

**Auto-goal selection:**
- If exactly one inference node is unreferenced → auto conjecture
- Otherwise requires explicit `--goal NODE_ID`

**`eprover.py`**: E-prover integration
- Calls E-prover ATP to check provability
- Parses results: theorem/unsat/sat/timeout
- Unicode handling with error fallback

**`tptp.py`**: TPTP serialization
- FOF (First-Order Form) format
- Axioms and conjectures

#### **F. Diagnostics** (`argir/diagnostics.py`)

**Issue Detection:**

1. **`unsupported_inference`**:
   - Premises don't entail conclusion
   - Checked via FOL and AF semantics
   - Most common issue type

2. **`circular_support`**:
   - Cycles in support/derivation graph
   - Uses NetworkX to detect cycles

3. **`contradiction_unresolved`**:
   - Contradicting atoms with opposite polarity
   - Mutual attacks between nodes

4. **`weak_scheme_instantiation`**:
   - Argumentation schemes missing critical question backing

5. **`goal_unreachable`**:
   - Goal not accepted under AF semantics

**Helper functions:**
- `is_node_accepted_in_af`: Check AF acceptance
- `extract_af_args_attacks`: Extract AF structure
- `check_inference_support`: Verify logical entailment

#### **G. Repairs** (`argir/repairs/`)

**Two repair strategies:**

**1. AF Enforcement** (`af_enforce.py`):
- **Goal**: Make goal node accepted under AF semantics
- **Method**: Add/remove attack edges
- **Verification**: Checks AF acceptance before/after
- **Kind**: "AF" repairs

**2. FOL Abduction** (`fol_abduction.py`):
- **Goal**: Find missing premises to prove conclusion
- **Method**:
  1. Enumerate candidate hypotheses (1-2 atoms)
  2. Test each with E-prover (axioms + hypothesis ⊢ goal)
  3. Check consistency (axioms + hypothesis ⊬ ⊥)
  4. Find minimal subset (irredundancy check)
- **Verification**: Comprehensive AF + FOL verification
- **Kind**: "FOL" repairs

**Repair Verification:**
- `af_goal_accepted`: Goal accepted after repair
- `fol_entailed`: Repair enables FOL proof
- `af_impact`: Before/after AF acceptance for target & goal

---

### 4. **Server & Frontend** (`server.py`, `frontend/`)

**FastAPI Server:**
- `/api/analyze`: Main analysis endpoint
- `/api/saved`: List saved queries
- `/api/saved/{hash}`: Retrieve saved query
- `/plain/{hash}/{format}`: Get results in various formats (md, txt, html, json, fol, apx)

**Features:**
- Request-scoped API keys (header or body)
- Query persistence (`saved/`)
- Results caching (`saved-results/`)
- Diagnosis & repair on-demand

**Frontend:**
- Vite/React UI
- Interactive argument graph visualization
- Multi-tab interface (Graph, Issues, Repairs, Details)
- Node selection and detail inspection
- Saved query browser

---

### 5. **Workflow Example**

```
User Input: "If it rains, the streets get wet. It is raining. So the streets are wet."

↓ [Soft Pipeline]

Stage 1: LLM Extraction (Soft IR)
  - Node C1: premise "raining"
  - Node C2: premise "streets_wet"
  - Node R1: rule (raining => streets_wet)
  - Node C3: conclusion "streets_wet" (premises: C1, R1)

↓ [Compilation]

Stage 2: Canonicalization
  - Normalize predicates: raining → raining, streets_wet → streets_wet
  - Build atom_lexicon: {raining: [...], streets_wet: [...]}
  - Create implicit rule if needed
  - Generate support edges from references

↓ [Validation]

  - Check lexicon completeness ✓
  - Check references ✓
  - Auto-patch any issues

↓ [Analysis]

AF Semantics (Clingo):
  - Extract args: [C1, C2, R1, C3]
  - Extract attacks: []
  - Compute grounded: {C1, C2, R1, C3} (all accepted)

FOL Translation (TPTP):
  - Axiom: raining
  - Axiom: raining => streets_wet
  - Conjecture: streets_wet

E-prover:
  - Result: Theorem (proved) ✓

↓ [Diagnosis] (if enabled)

  - Check unsupported inferences: None
  - Check circular support: None
  - Check contradictions: None
  Issues: [] (no issues detected)

↓ [Report]

Markdown report with:
  - Graph structure (nodes, edges)
  - AF semantics results
  - FOL axioms + proof status
  - Issues (if any)
  - Repairs (if generated)
```

---

### 6. **Statistics System** (`saved_stats.py`)

**Purpose**: Analyze all saved queries to understand system performance and patterns.

**Data Sources:**
- Query parameters: `saved/` directory
- Analysis results: `saved-results/` directory (cached)

**Statistics Collected:**

**Graph Structure:**
- Nodes, edges, connected components
- Graph density
- Edge type breakdown (support vs attack)

**Issues:**
- Total issues and per-query statistics (avg, min, max)
- Issue type distribution (unsupported_inference, contradiction_unresolved, circular_support)
- Queries with no issues

**Repairs:**
- Total repairs and per-query statistics
- Repair kinds (FOL vs AF)
- Verification success rate

**FOL Prover:**
- Result distribution (theorem, unknown, unsat, sat, timeout)

**Correlations:**
- Graph complexity vs issues
- Graph connectedness vs FOL provability

**CLI Usage:**
```bash
# Generate summary statistics
python3 saved_stats.py

# Analyze specific queries
python3 saved_stats.py --filter hash1,hash2

# JSON output
python3 saved_stats.py --format json

# Detailed per-query data
python3 saved_stats.py --detailed --format csv
```

---

## Design Philosophy

1. **Separation of concerns**: Soft extraction (LLM) vs canonicalization (deterministic)
2. **Dual semantics**: AF (dialectical) + FOL (logical)
3. **Automated repair**: Not just diagnosis, but actionable fixes
4. **Verification**: Every repair is verified for correctness
5. **Caching**: LLM responses + analysis results cached for efficiency
6. **Strict contracts**: Pydantic models ensure type safety
7. **Extensibility**: Pluggable repair strategies, multiple AF semantics

---

## Key File Locations

### Core Pipeline
- `argir/pipeline.py` - Main pipeline orchestration (strict & soft)
- `argir/core/model.py` - Pydantic data models (ARGIR, Statement, Rule, etc.)
- `argir/compile_soft.py` - Soft IR → Strict ARGIR compilation
- `argir/canonicalize.py` - AtomTable and predicate canonicalization

### Natural Language Processing
- `argir/nlp/llm.py` - LLM client (Gemini API)
- `argir/nlp/parse.py` - Extraction prompts and parsing
- `argir/prompts.py` - System prompts for soft extraction

### Validation
- `argir/validate.py` - ARGIR validation and patching
- `argir/checks/rules.py` - Structural checks
- `argir/checks/strict.py` - Strict validation

### Semantics & FOL
- `argir/semantics/af_clingo.py` - Clingo-based AF semantics
- `argir/semantics/semantics.py` - Compute extensions
- `argir/fol/translate.py` - ARGIR → FOL translation
- `argir/fol/eprover.py` - E-prover integration
- `argir/fol/tptp.py` - TPTP serialization

### Diagnosis & Repair
- `argir/diagnostics.py` - Issue detection (unsupported inference, contradictions, etc.)
- `argir/repairs/fol_abduction.py` - FOL-based abductive repair
- `argir/repairs/af_enforce.py` - AF-based enforcement repair
- `argir/repair_types.py` - Issue, Repair, Patch, Verification types
- `argir/reporting.py` - Diagnosis report rendering

### Server & Frontend
- `server.py` - FastAPI server with analysis endpoints
- `frontend/` - Vite/React web UI
- `saved_stats.py` - Statistics analysis tool

### Reports
- `argir/report/render.py` - Markdown report generation

---

## Environment Variables

- `GEMINI_API_KEY` - Gemini API key for LLM access
- `GOOGLE_CLOUD_PROJECT` - GCP project (alternative to API key)
- `GOOGLE_CLOUD_LOCATION` - GCP region
- `LLM_MODEL` - Model name (default: `gemini-2.5-flash`)
- `CACHE_LLM` - Enable LLM response caching (recommended)
- `LLM_CACHE_DIR` - Cache directory (default: `.cache/llm`)

---

## Dependencies

**Core:**
- `pydantic>=2.0` - Data validation and models
- `google-genai` - Gemini LLM client
- `clingo` - ASP solver for AF semantics
- `spacy` - NLP for lemmatization
- `networkx` - Graph algorithms (cycle detection)
- `joblib` - LLM response caching

**Server:**
- `fastapi` - Web API framework
- `uvicorn` - ASGI server

**External (optional):**
- `eprover` - Automated theorem prover (install via package manager)

---

## Testing

Run tests with:
```bash
python tests/run.py --soft
```

Make sure to set `CACHE_LLM=true` to avoid redundant LLM calls during testing.

---

## Common Workflows

### Analyzing a Text Argument (CLI)
```bash
# Basic analysis
python -m argir.cli examples/sample.txt --out out

# With soft pipeline (recommended)
python -m argir.cli examples/sample.txt --out out --soft

# With diagnosis and repair
python -m argir.cli examples/sample.txt --out out --soft --diagnose --repair
```

### Analyzing via API
```python
from argir.pipeline import run_pipeline_soft

text = "If it rains, the streets get wet. It is raining. So, the streets are wet."
result = run_pipeline_soft(text, fol_mode="classical", k_samples=3)

print(result["report_md"])
```

### Generating Statistics
```bash
# All saved queries
python3 saved_stats.py > stats.txt

# Specific query
python3 saved_stats.py --filter 011f93a319a0
```

---

## Version

Current version: 0.3.3 (check `argir/__init__.py`)
