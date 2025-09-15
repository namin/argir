# ARGIR Soft‑IR & Soft Semantic Parser — **Design (Revised)**

## 0. Abstract

We moved from “one‑shot strict ARGIR” to a **funnel**:

> **LLM → Soft‑IR (permissive)** → **LLM repairs (semantic harmonization)** → **deterministic compiler** (canonicalization, entity factoring, graph assembly, validation, implicit rules) → **strict ARGIR** → **AF/FOL export**.

This document specifies the **IRs**, the **soft semantic parser**, the **LLM repair passes**, and the **compiler/validator** that bridge them. The goal is to maximize robustness and auditability while keeping the final **ARGIR contract strict** and stable—and to ensure all proofs are **non‑vacuous**.

---

## 1. Motivation & Background

One‑shot ARGIR caused frequent validation failures (dangling refs, non‑canonical atoms, brittle lexicon) and hid reasoning errors (vacuous proofs). We now:

* Let the LLM focus on **semantics** (Soft‑IR).
* Apply **targeted LLM repairs** to harmonize surface variation (predicate and polarity unification; rule exceptions infill) while keeping semantics visible.
* Push **syntax/canonicalization/topology** into deterministic code.
* Add **implicit rule synthesis**, **orphan‑premise → fact promotion**, **goal selection heuristics**, **entity extraction**, and **invariants** (“not‑all” goal shape) to improve proofability and correctness.
* Remove per‑node linkage axioms so FOL proofs are **earned** from rules and facts.

---

## 2. Goals / Non‑Goals

**Goals**

* A permissive **Soft‑IR** that LLMs can emit reliably.
* Targeted **LLM repairs** (post‑extraction, pre‑compile) for:

  * predicate unification (surface variants),
  * **polarity/antonym** unification (e.g., immortal ↔ ¬mortal),
  * exception extraction for defeasible rules (when missed).
* Deterministic compilation to **strict ARGIR** with:

  * canonical predicates & arities,
  * referential integrity,
  * complete lexicon of canonical→surface,
  * implicit rules synthesized when a node has premises+conclusion but no rule.
* Clean, **non‑vacuous** **FOL (TPTP)** export (no per‑node `(prem ⇒ concl)` shortcuts).
* Sensible **auto‑goal selection**.
* **Entity extraction** to factor proper nouns into arguments.
* **Invariants**: no fused/macro predicates; “not‑all” goals encoded as existential counterexamples.
* Clear validators, typed issues, and deterministic patchers.

**Non‑Goals (now)**

* Full semantic typing & quantifier calculus.
* Full bipolar AF semantics (we export Dung AF; supports are for UI).
* Heavy NLP dependencies; where semantics is needed, prefer **LLM repairs** over lexical heuristics.

---

## 3. Terminology

* **Soft‑IR:** LLM‑friendly, permissive JSON.
* **LLM repairs:** small, auditable post‑extraction adjustments (predicate/polarity unification; exceptions infill).
* **ARGIR (strict):** canonicalized, validated graph IR with required lexicon.
* **Statement/Atom:** predicate with 0..n arguments.
* **Rule node:** explicit inference schema `Antecedents ⇒ Consequents [except …]`.
* **Implicit rule:** synthesized when a node has premises+conclusion but no rule.
* **Orphan premise:** a premise statement not concluded elsewhere; promoted to FOL **fact**.
* **Attack kinds:** `rebut` (claim vs claim), `undercut` (attack on inference).

---

## 4. Architecture & Data Flow

```
[Raw Text]
    │
    ├─(S0) Preprocess (sentences, spans)
    │
    ├─(S1) LLM Soft Extraction  ───────────►  [Soft‑IR]
    │
    ├─(S1b) LLM Repairs (post‑extraction) ─►  predicate & polarity unification,
    │                                          exceptions infill, (no macro preds)
    │
    ├─(S2) Canonicalization & Entity Extraction
    │       - canonical predicate keys (minimal normalization)
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
    │       - invariants: “not‑all” goal shape, no fused/macro preds
    │
    ├─(S5) Scoring & Best‑of‑k (optional)
    │
    ├─(S6) Strict ARGIR (with metadata.atom_lexicon)
    │
    ├─(S7) AF Export (Dung)   ─► apx
    └─(S8) FOL Export (TPTP)  ─► fof.p (with goal selection; non‑vacuous)
```

---

## 5. IR Specifications

### 5.1 Soft‑IR (permissive)

**Version:** `soft-0.1`

**Top‑level**

```json
{
  "version": "soft-0.1",
  "source_text": "…",
  "spans_indexed": true,
  "graph": { "nodes": [ ... ], "edges": [ ... ] },
  "metadata": { }
}
```

**Types**

* `Span`: `{ "start": int, "end": int }`
* `Term`: `{ "kind": "Const" | "Var" | "Act" | "Num" | "Str", "name": "…" , "sort"?: "…" }`
* `SoftStatement`:

  ```json
  {
    "pred": "string (free form)",
    "args": [Term, ...],
    "polarity": "pos" | "neg",
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
* `SoftNode` / `SoftEdge`: as before.

**Notes & **Hard constraints** for Soft‑IR**

* **Never** emit **fused/macro predicates** that combine class + property (e.g., `bird_can_fly`); represent them as **rule** + separate predicates (`bird(X)`, `fly(X)` or `can_fly(X)`).
* **Negated universals** (“not all / not every …”) **must** be encoded as an **existential counterexample GOAL** with two statements and an `exists` quantifier:

  * `S(X)` and **negated** property `¬P(X)` (via `polarity: "neg"` on the property statement).
    (Polarity unification may later map `immortal` → `mortal` with negative polarity; keep the negative property visible in Soft‑IR for auditability.)

---

### 5.2 ARGIR (strict)

* All statements contain **canonicalized atoms**:

  ```json
  "atoms": [{ "pred": "canonical_key", "args": [Term,...], "negated": false }]
  ```
* All `Ref`s resolve; lexicon maps `canonical_key` → surface examples.
* IDs: `C#` (facts), `P#` (inferences), `R#` (rules), `IR_*` (implicit rules).

**Invariants**

* Canonical predicate keys are lowercase with underscores; no embedded entity names when extractable.
* **No fused/macro predicates** make it into strict ARGIR; violations fail validation.
* **Negated‑universal goal invariant** holds (or the run fails fast).

---

## 6. Soft Semantic Parser

### 6.1 Responsibilities

* Convert raw text into Soft‑IR:

  * segment nodes,
  * extract supports/attacks,
  * propose **rule nodes** for generalizations,
  * keep **predicate strings short**; arguments as `Const` when obviously entities,
  * annotate spans/rationales when easy.

### 6.2 Prompting (system sketch)

* System prompt defines schema + **explicit prohibitions** (no macro preds) and **required shapes** (negated‑universal → existential counterexample).
* Few‑shot motifs: modus ponens, exceptions (“unless”, “however … sometimes”), rebut vs undercut, quantifiers.
* Constraints: prefer `polarity` over `not_*` keys; allow `Ref` premises; leave `span` empty if unsure.

### 6.3 Best‑of‑k (optional)

* Sample **k** Soft‑IRs.
* Compile, validate, score (errors, warnings, #implicit rules, AF/FOL cleanliness, predicate economy, proof success).
* Pick best; optionally union non‑conflicting supports.

---

## 7. LLM Repairs (post‑extraction, pre‑compile)

* **Predicate unification:** map surface variants to shared canonical keys.
* **Polarity/antonym unification:** map antonyms to a canonical predicate with polarity (e.g., `immortal` → `mortal` with negative polarity; handles double negation).
* **Exception infill:** when the text clearly contains exception cues but `rule.exceptions` is empty, add exceptions as positive statements (lowered later as guards).

> Repairs keep semantics **visible**; they do not collapse structure or hide antonymy. No lexical heuristics—LLM‑first by design.

---

## 8. Compiler: Soft‑IR → ARGIR

### 8.1 Canonicalization

* Minimal normalization (lowercase, collapse spaces → `_`).
* Entity extraction moves proper nouns to arguments.
* Polarity moves from Soft‑IR `polarity` to `negated` on atoms.

### 8.2 Graph assembly & IDs

* Assign `C#`, `P#`, `R#`, `IR_*`; resolve refs; deduplicate identical statements.

### 8.3 Validators & deterministic patchers

**Issue taxonomy** (examples as before) plus:

* `FUSED_PREDICATE`: fused/macro predicate detected → **fail**.
* `NOT_ALL_GOAL_SHAPE`: negated‑universal goal not in existential counterexample form → **fail**.

**Compiler actions**

* **Implicit rule synthesis** when a node has premises+conclusion but no rule (yields `IR_*` rule node).
* **Orphan promotion:** premise‑only statements become facts.
* **No node‑link axioms:** we **do not** emit `(premises ⇒ conclusion)` axioms for inference nodes.

---

## 9. Exports

### 9.1 AF (Dung) export

* Arguments exclude `IR_*`; attacks include `rebut` and `undercut`. Supports are UI‑only.

### 9.2 FOL (TPTP) export — **non‑vacuous by construction**

* **Facts:** all `C#` conclusions + orphan premises.
* **Rule axioms:** one `fof(rule_*, axiom, …)` per explicit or **implicit** rule.

  * **Defeasible mode:** exceptions become guards:
    `Antecedents ∧ ¬Exc₁ ∧ ¬Exc₂ ∧ … ⇒ Consequent`
    (All variables from ants/cons/excs are universally quantified.)
  * **Classical mode:** exceptions are **ignored by design** (rule is just `Antecedents ⇒ Consequent`).
* **No node links:** **never** emit `fof(node_*, axiom, (prem ⇒ concl))`.
* **Goal selection (default):** sink in attack subgraph; prefer negated claims; more premise‑rich; otherwise last “therefore” claim.

---

## 10. Public Interfaces

*(As before; updated comments to reflect “no node links” and “defeasible guards”)*

```python
def export_fof(argir_obj: dict, *, goal: str | None = None,
               mode: Literal["classical","defeasible"]="classical") -> str:
    """Return TPTP. Emits facts, explicit/implicit rule axioms; never per-node links.
       In 'defeasible' mode, exceptions are conjoined as negated guards."""
```

---

## 11. Testing & Evaluation

**Unit tests**

* Canonicalization: normalization; arity suffixing; alias merges.
* Entity extraction.
* Implicit rule synthesis.
* Orphan promotion.
* **Exception lowering:** multiple exceptions become **conjoined negated guards**; all vars quantified.

**Property & metamorphic tests**

* Idempotence, permutation invariance, paraphrase invariance, round‑trip.

**Invariants (fail‑fast)**

* **No fused predicates** in Soft‑IR.
* **Negated‑universal goal shape** present when source contains “not all / not every”.

**End‑to‑end**

* Proof success rate (classical vs defeasible).
* Predicate economy.
* Validator noise.

---

## 12. Performance & Observability

* Deterministic passes are linear in graph size; best‑of‑k adds O(k).
* Logs:

  * canonicalization & alias merges,
  * repairs (predicate, polarity, exceptions),
  * validator issues, invariants,
  * goal selection rationale,
  * proof summary (SZS Theorem/Unknown/CounterSatisfiable).
* Persist `AtomTable` per project to stabilize canonical forms.

---

## 13. Versioning & Compatibility

* Soft‑IR `version`: `soft-0.1` (current). Backward‑compatible additions only.
* ARGIR versioning follows repo releases.
* Lexicon format is stable: `canonical → [surface examples]`.

---

## 14. Security & Safety

* Treat model output as untrusted:

  * strict JSON parsing; resource caps,
  * strip control chars from surfaces,
  * record model ID/temperature/seed for reproducibility.

---

## 15. Open Questions

* **Deontics/action reification** for “should/should not”.
* **Undercut vs rebut export** (UI only; AF remains attack‑only).
* **Lightweight sorts/types** to aid unification.
* **Ability vs actuality policy** (`can_fly` vs `fly`)—now clean via no‑macro rule + LLM unification; consider an optional defeasible bridge rule when licensed by text.

---

## 16. Appendix A — Minimal JSON Schemas

*(Same as previous; unchanged except for the Soft‑IR hard constraints noted above.)*

---

## 17. Appendix B — Worked Micro‑Example

**Text**: “If it rains, streets are wet. It rains. Therefore, streets are wet.”

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

**Strict ARGIR → FOL**
Facts: `rain(city)`
Rule: `∀x (rain(x) ⇒ street_wet(x))`
Goal: `street_wet(city)` → **Theorem** (no node‑link axioms used).

---

## Changelog (vs. prior doc)

* Added **S1b LLM repairs** stage and described the specific repairs.
* Strengthened **Soft‑IR constraints**: **no fused/macro predicates**; explicit **negated‑universal** goal shape.
* Rewrote **FOL export** to **never** emit per‑node link axioms; rule axioms only (explicit + implicit).
* Clarified **defeasible exception lowering**: **conjoined negated guards** (and variable quantification).
* Added **fail‑fast invariants** and CI‑style checks for “not‑all” and fused predicates.
* Emphasized **auditability**: negative properties remain visible in Soft‑IR; polarity mapping is explicit.

