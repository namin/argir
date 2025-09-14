# ARGIR Soft‑IR & Soft Semantic Parser — Design

## 0. Abstract

We moved from "one‑shot strict ARGIR" to a **funnel**:

> **LLM → Soft‑IR (permissive)** → **deterministic compiler** (canonicalization, entity factoring, graph assembly, validation, auto‑repair, implicit rules) → **strict ARGIR** → **AF/FOL export**.

This document specifies the **IRs**, the **soft semantic parser**, and the **compiler/validator** that bridge them. The goal is to maximize robustness while keeping the final **ARGIR contract strict** and stable.

---

## 1. Motivation & Background

One‑shot ARGIR caused frequent validation failures (dangling refs, non‑canonical atoms, brittle lexicon). We now:

* Let the LLM focus on **semantics** (Soft‑IR).
* Push **syntax/canonicalization/topology** into deterministic code.
* Add **implicit rule synthesis**, **orphan‑premise → fact promotion**, **goal selection heuristics**, and **entity extraction** (subject‑as‑argument) to improve proofability and compositionality.

---

## 2. Goals / Non‑Goals

**Goals**

* A permissive **Soft‑IR** that LLMs can emit reliably.
* Deterministic compilation to **strict ARGIR** with:
  * canonical predicates & arities,
  * referential integrity,
  * complete lexicon of canonical→surface,
  * implicit rules synthesized when premises→conclusion lacks a rule.
* Clean **FOL (TPTP)** export (no duplication, no spurious negatives).
* Sensible **auto‑goal selection** for typical argumentative prose.
* Entity extraction to factor proper nouns into **arguments**.
* Clear validators, typed issues, and deterministic patchers.

**Non‑Goals (now)**

* Full semantic typing & quantifier calculus.
* Full bipolar AF semantics. (We export Dung AF; support edges are for UI.)
* Heavy NLP dependencies; we prefer deterministic heuristics + LLM when needed.

---

## 3. Terminology

* **Soft‑IR:** LLM‑friendly, permissive JSON.
* **ARGIR (strict):** canonicalized, validated, graph IR with required lexicon.
* **Statement/Atom:** predicate with 0..n arguments.
* **Rule node:** explicit inference schema `Antecedents ⇒ Consequents [except …]`.
* **Implicit rule:** auto‑synthesized rule when a node has premises+conclusion but no rule.
* **Orphan premise:** a premise statement not concluded elsewhere; promoted to FOL **fact**.
* **Attack kinds:** `rebut` (claim vs claim), `undercut` (attack on inference).

---

## 4. Architecture & Data Flow

```
[Raw Text]
    │
    ├─(S0) Preprocess (sentences, spans)
    │
    ├─(S1) LLM Soft Extraction  ──►  [Soft‑IR]
    │
    ├─(S2) Canonicalization & Entity Extraction
    │       - canonical predicate keys
    │       - factor proper nouns to Const terms
    │       - alias/merge map, arity checks
    │
    ├─(S3) Graph Assembly
    │       - assign stable node IDs (C#, P#, R#, IR_#)
    │       - resolve Refs, dedup, structural invariants
    │
    ├─(S4) Validator & Patchers
    │       - missing lexicon, dangling refs, arity/type
    │       - synthesize implicit rules
    │       - promote orphan premises to facts
    │
    ├─(S5) Scoring & Best‑of‑k (optional)
    │
    ├─(S6) Strict ARGIR (with metadata.atom_lexicon)
    │
    ├─(S7) AF Export (Dung)   ─► apx
    └─(S8) FOL Export (TPTP)  ─► fof.p (with goal selection)
```

---

## 5. IR Specifications

### 5.1 Soft‑IR (permissive)

**Version:** `soft-0.1` (string)

**Top‑level**

```json
{
  "version": "soft-0.1",
  "source_text": "…",
  "spans_indexed": true,           // optional; if true, try to fill Span objects
  "graph": { "nodes": [ ... ], "edges": [ ... ] },
  "metadata": { }
}
```

**Types**

* `Span`: `{ "start": int, "end": int }` (byte or char offsets; doc‑relative)
* `Term`: `{ "kind": "Const" | "Var" | "Act" | "Num" | "Str", "name": "…" , "sort"?: "…" }`
* `SoftStatement`:
  ```json
  {
    "pred": "string (free form)",
    "args": [Term, ...],
    "polarity": "pos" | "neg",     // preferred in Soft‑IR
    "span"?: Span, "rationale"?: "…", "confidence"?: number
  }
  ```
* `SoftPremiseRef`: `{ "kind": "Ref", "ref": "nodeId", "note"?: "…" }`
* `SoftRule`:
  ```json
  {
    "name"?: "…", "strict"?: boolean, "scheme"?: "…",
    "antecedents": [SoftStatement, ...],
    "consequents": [SoftStatement, ...],
    "exceptions":  [SoftStatement, ...],
    "span"?: Span, "rationale"?: "…"
  }
  ```
* `SoftNode`:
  ```json
  {
    "id"?: "string",
    "premises": [SoftStatement | SoftPremiseRef, ...],
    "rule"?: SoftRule,
    "conclusion"?: SoftStatement,
    "span"?: Span, "rationale"?: "…"
  }
  ```
* `SoftEdge`:
  ```json
  {
    "source": "nodeId",
    "target": "nodeId",
    "kind": "support" | "attack",
    "attack_kind"?: "rebut" | "undercut",
    "rationale"?: "…"
  }
  ```

**Notes**

* Soft‑IR favors **short, contentful predicate strings**; modality/negation can be in `polarity` and/or in the predicate text. The compiler normalizes these.
* Arguments **should** be emitted as `Term` when easy (e.g., `Const: diablo_canyon`). If not, leave empty; the compiler can still work.

---

### 5.2 ARGIR (strict)

**Differences from Soft‑IR**

* All statements contain **canonicalized atoms**:
  ```json
  "atoms": [ { "pred": "canonical_key", "args": [Term,...], "negated": false } ]
  ```
* All `Ref` targets resolve; no dangling references.
* **Lexicon is required**: `metadata.atom_lexicon` maps `canonical_key` → array of **surface examples**.
* Node ID conventions:
  * `C#` = fact (no premises, no rule).
  * `P#` = premise(s) → conclusion (may reference rule).
  * `R#` = explicit rule node (if modeled separately).
  * `IR_*` = synthesized implicit rule node (internal).
* **Implicit rules** are inserted where a node has premises+conclusion but no rule.
* **Entity extraction** factors proper nouns into `Const` terms (e.g., `operates_normally_safely(diablo_canyon)`).

**Invariants**

* Every atom's `pred` is canonical (lowercase, underscore‑separated; no leading/trailing `_`; no embedded entity names when extractable).
* `metadata.atom_lexicon` **preserves surface forms** (canonical key is *not* duplicated as an example unless no surface is available).
* No cycles that violate rule constraints; self‑loops forbidden.
* AF export lists **arguments** only (IR nodes excluded).

---

## 6. Soft Semantic Parser

### 6.1 Responsibilities

* Convert raw text into **Soft‑IR**:
  * segment into nodes (claims, premises),
  * extract relations (support/attack),
  * propose rules (when explicit cues are present),
  * suggest predicate strings & arguments (when trivial),
  * annotate spans and rationales where easy.

* Keep output **valid JSON** and **lightly structured**, not canonical.

### 6.2 Prompting (system sketch)

* **System prompt:** "You convert natural language into a *Soft IR*… (schema + examples). Keep predicates short; avoid articles/auxiliaries; arguments as `Const` when it's obviously a named entity."
* **Few‑shot 'micro‑motifs':**
  * Modus ponens, exception ("unless"), rebut vs undercut, normative "should/should not", quantifier "some/most/no".
* **Constraints:**
  * Prefer `polarity` over encoding `not_*` in predicate.
  * Allow `Ref` premises to earlier nodes.
  * Leave `span` empty if unsure; the compiler can still proceed.

### 6.3 Best‑of‑k sampling & selection (optional)

* Sample **k** Soft‑IRs at low temperature.
* Compile, validate, and **score** candidates:
  * errors (weighted), warnings,
  * \#implicit rules synthesized,
  * AF/FOL export cleanliness,
  * predicate economy (fewer distinct canonical keys),
  * proof success if goal derivable.
* Pick best; optionally union non‑conflicting supports.

---

## 7. Compiler: Soft‑IR → ARGIR

### 7.1 Canonicalization

* **Normalize predicate keys**
  Lowercase; trim; collapse whitespace; replace spaces with `_`; strip leading articles/auxiliaries; collapse repeated underscores; drop trailing underscores.
  If arity clash, suffix with `_2`, `_3`, etc.

* **Entity extraction**
  Heuristics:
  * Proper nouns & known facility names → `Const` (`diablo_canyon`).
  * Patterns that start with a proper noun (e.g., `Diablo_Canyon_*`) → factor into arguments:
    * `Diablo_Canyon_operates_normally_safely` → `operates_normally_safely(diablo_canyon)`

* **Alias & merge**
  Maintain `AtomTable` with:
  * `entries: canonical_key → {arity, examples[]}`
  * `alias: normalized_surface → canonical_key`
  Similarity + arity check merges; otherwise create a new canonical key.

* **Polarity**
  Convert Soft‑IR `polarity` to `negated` boolean on atoms. Prefer **positive predicates** with negation in the atom, not in the key.

### 7.2 Graph assembly & IDs

* Assign IDs:
  * `C#` for nodes with conclusion but no premises & no rule (facts).
  * `P#` for nodes with premises and/or rule and a conclusion.
  * `IR_P#` for synthetic rule nodes attached to a specific `P#`.
* Resolve Refs; build edges; deduplicate nodes with identical `(atom, args, neg)`.

### 7.3 Validators & deterministic patchers

**Issue taxonomy (examples)**

| Code               | Meaning                                | Patcher                                        |
| ------------------ | -------------------------------------- | ---------------------------------------------- |
| `MISSING_LEXICON`  | atom pred not listed in `atom_lexicon` | Add canonical→surface via `AtomTable`          |
| `DANGLING_REF`     | reference to unknown node              | materialize placeholder or drop (configurable) |
| `ARITY_MISMATCH`   | observed vs canonical arity differs    | reslot/drop surplus arg (heuristic)            |
| `DERIVABILITY_GAP` | premises+conclusion but no rule        | synthesize `IR_*` node                         |
| `MULTI_ARITY_PRED` | same key used with multiple arities    | suffix canonical (\_2) or split                |

**Additional compiler actions**

* **Implicit rule synthesis**: for each `P#` with premises+conclusion but no rule, create `IR_P#` with the antecedents/consequent extracted from the node's own premise/conclusion statements.
* **Orphan premise promotion**: any `Stmt` appearing as a premise and not concluded elsewhere becomes a FOL **fact**.
* **No rule duplication**: if a node is supported by an explicit rule node, **do not** repeat that rule inside `node_*_link` axioms.

---

## 8. Exports

### 8.1 AF (Dung) export

* Arguments: **exclude** `IR_*` nodes.
* Attacks: include `rebut` and `undercut` as `att(A,B)`; keep `attack_kind` in UI only.
* Supports: not serialized into Dung AF (they're shown in UI).

### 8.2 FOL (TPTP) export

* **Facts:**
  * any `C#` conclusion,
  * plus orphan premises promoted to facts.
* **Rule axioms:** one `fof(rule_*, axiom, (A & … => C)).` per explicit or implicit rule.
* **Node links:** for nodes with **no rule**, emit `fof(node_P#, axiom, (premises => conclusion)).`
* **Goal selection (default):**
  1. Sink in the **attack** subgraph,
  2. Prefer **negated "should not …"** conclusions when present,
  3. Higher derivational complexity (more premises),
  4. Otherwise, last "therefore"‑like node by position.
* **No spurious negatives:** only goals and explicitly negated **conclusions** introduce `~`; attacks never produce `~P` *facts*.

---

## 9. Public Interfaces

### 9.1 Python API

```python
def llm_soft_extract(text: str, *, k: int = 1, seed: int | None = None) -> list[SoftIR]:
    """Call the model with the Soft‑IR prompt; return k candidates."""

def compile_soft_ir(soft: SoftIR, existing_atoms: AtomTable | None = None
                   ) -> tuple[dict, AtomTable, ValidationReport]:
    """Deterministically compile to strict ARGIR (dict), return AtomTable + report."""

def validate_argir(argir_obj: dict) -> ValidationReport:
    """Run validators & return typed issues."""

def export_af(argir_obj: dict) -> str:
    """Return Dung AF apx text (args/att). IR_* nodes excluded."""

def export_fof(argir_obj: dict, *, goal: str | None = None, mode: Literal["classical","defeasible"]="classical"
              ) -> str:
    """Return TPTP string. Handles orphan facts, rules, node links, goal selection."""
```

### 9.2 CLI

```
argir --soft --k-samples 3 --mode classical --goal P3 --out out/ …
```

Artifacts:
* `draft.json` (Soft‑IR),
* `argir.json` (strict ARGIR),
* `validation.json` (issues),
* `af.apx`, `fof.p`, `eprover.log`,
* `stats.json` (optional metrics: #atoms, #rules, proof result, etc.).

---

## 10. Testing & Evaluation

**Unit tests**

* Canonicalization: string normalization, arity suffixing, alias merges, double underscore collapse.
* Entity extraction: `Diablo_Canyon_*` → `*(diablo_canyon)`.
* Implicit rule synthesis: premises+conclusion → `IR_P#` created.
* Orphan promotion: premise‑only statements become facts.

**Property & metamorphic tests**

* **Idempotence:** compiling strict ARGIR twice is a no‑op.
* **Permutation invariance:** sentence order shuffles don't change final ARGIR.
* **Paraphrase invariance:** synonyms don't explode the lexicon.
* **Round‑trip:** serialize → parse → serialize equals original (strict).

**End‑to‑end**

* Corpus acceptance: % runs producing valid ARGIR without manual fixes.
* Proof success: % goals with `SZS Theorem` (classical mode).
* Predicate economy: ratio (unique canonical predicates / tokens).
* Validator noise: avg # warnings (target near zero on clean texts).

---

## 11. Performance & Observability

* Deterministic passes are linear in #nodes + #statements.
* `best‑of‑k` adds O(k) compile/validate/export cost; k is small (≤5).
* Log:
  * canonicalization decisions (new vs merged canonical keys),
  * validator issues and applied patchers,
  * goal selection rationale,
  * proof summary (sat/unsat/theorem).
* Persist `AtomTable` per project to stabilize canonical forms.

---

## 12. Versioning & Compatibility

* **Soft‑IR `version`:** `soft-0.1` (current). Backward compatible additions should only add optional fields.
* **ARGIR `version`:** increments in lockstep with repo releases (`0.4.x`).
* Lexicon format is stable: `canonical → [surface examples]`.

---

## 13. Security & Safety

* Treat model output as untrusted:
  * parse JSON robustly; reject large payloads,
  * cap nodes/edges to avoid pathological prompts,
  * never execute embedded code,
  * strip control characters from surface examples.
* Record the model ID/temperature/seed for reproducibility.

---

## 14. Open Questions

* **Deontics/action reification:** Represent `should_not(suggest_closure(we, dc))` explicitly? (Recommended next.)
* **Undercut vs rebut export:** Keep both in UI; Dung AF remains attack‑only.
* **Lightweight sorts/types:** Introduce `sort(plant, diablo_canyon)` facts to aid unification without changing user‑visible output.
* **Quantifiers:** Minimal encoding for `some/most/no` to distinguish claims.

---

## 15. Appendix A — Minimal JSON Schemas (informal)

**Soft‑IR (informal)**

```json
SoftIR = {
  version: string,
  source_text: string,
  spans_indexed?: boolean,
  graph: { nodes: SoftNode[], edges: SoftEdge[] },
  metadata?: object
}

SoftNode = {
  id?: string,
  premises: (SoftStatement | SoftPremiseRef)[],
  rule?: SoftRule,
  conclusion?: SoftStatement,
  span?: Span,
  rationale?: string
}

SoftStatement = {
  pred: string,
  args: Term[],
  polarity?: "pos" | "neg",
  span?: Span, rationale?: string, confidence?: number
}

Term = { kind: "Const" | "Var" | "Act" | "Num" | "Str", name: string, sort?: string }
SoftPremiseRef = { kind: "Ref", ref: string, note?: string }
SoftRule = { name?: string, strict?: boolean, scheme?: string,
             antecedents: SoftStatement[], consequents: SoftStatement[], exceptions?: SoftStatement[],
             span?: Span, rationale?: string }
SoftEdge = { source: string, target: string, kind: "support" | "attack", attack_kind?: "rebut" | "undercut",
             rationale?: string }
Span = { start: int, end: int }
```

**ARGIR (differences only)**

```json
StrictStatement = {
  kind: "Stmt",
  text?: string,
  atoms: [{ pred: string /* canonical */, args: Term[], negated: boolean }],
  quantifiers?: [], span?: Span, rationale?: string, confidence?: number
}

ARGIR = {
  version: string,
  source_text: string,
  spans_indexed?: boolean,
  graph: { nodes: StrictNode[], edges: SoftEdge[] },
  metadata: { atom_lexicon: { [canonicalPred: string]: string[] },
              implicit_rules_synthesized?: boolean }
}
```

---

## 16. Appendix B — Worked Micro‑Example

**Text**: "If it rains, streets are wet. It rains. Therefore, streets are wet."

**Soft‑IR (abbrev)**

```json
{
  "version": "soft-0.1",
  "source_text": "…",
  "graph": {
    "nodes": [
      { "id": "r1",
        "rule": { "strict": true,
          "antecedents":[{"pred":"rain","args":[{"kind":"Const","name":"city"}]}],
          "consequents":[{"pred":"street_wet","args":[{"kind":"Const","name":"city"}]}]
        }
      },
      { "id": "p1",
        "premises":[{"pred":"rain","args":[{"kind":"Const","name":"city"}]}],
        "conclusion":{"pred":"street_wet","args":[{"kind":"Const","name":"city"}]}
      }
    ],
    "edges":[{"source":"r1","target":"p1","kind":"support"}]
  }
}
```

**Strict ARGIR (abbrev)**

* Canonical preds: `rain(location)`, `street_wet(location)`
* Facts: `rain(city)`
* Rule axiom: `rain(x) => street_wet(x)`
* Goal auto‑selected: `street_wet(city)` → **Theorem**.

---

## 17. Acceptance Criteria (for this design)

* LLM can emit Soft‑IR that compiles to strict ARGIR **≥95%** of runs on the sample corpus (no manual edits).
* AF export excludes IR nodes; APX contains **args/att** only.
* FOL exporter:
  * does **not** duplicate rules in node links,
  * promotes orphan premises to **facts**,
  * never emits unmotivated negative **facts**,
  * proves the auto‑selected goal (or clearly reports `Satisfiable` when appropriate).
* Lexicon contains **surface examples** (canonical used as fallback only).
* Entity extraction active for obvious proper‑noun‑headed predicates.

