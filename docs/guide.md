# ARGIR: End‑to‑End Overview

**Purpose (one sentence):**
ARGIR turns natural‑language (NL) arguments into a **strict, analyzable graph**, diagnoses logical issues, and—when possible—proposes **minimal, machine‑checkable repairs** that are verified with formal tools.

**Key ideas:**

* A **Strict IR (intermediate representation)** captures *claims/premises*, *supports/attacks*, and *content atoms* (`pred(args)`).
* A projection to an **Abstract Argumentation Framework (AF)** (nodes = arguments, edges = attacks) lets us run **semantics** in a solver (Clingo).
* A lowering to **First‑Order Logic (FOL)** in TPTP lets us prove or refute claims with **E‑prover**.
* **Diagnosis** = identify issues (unsupported inference, circularity, contradictions, unreachable goals…).
* **Repair** = propose minimal edits (add missing premise, add/remove an attack, introduce a defender) **and verify** they have the intended effect.

> **Result files:**
>
> * `report.md` — human‑readable analysis with “Issue Cards”
> * `issues.json` — machine‑readable diagnoses
> * `repairs.json` — machine‑readable patches + verification

---

## High‑Level Flow

```
Natural language text
        │
        ▼
  (Soft extraction)
  ───────────────────────────────────────
  Heuristic/LLM-ish pass produces a rough graph,
  atoms, and (sometimes) implicit rule nodes
  ───────────────────────────────────────
        │
        ▼
    Strict IR (ARGIR JSON)
  nodes: Premise / Inference / Claim
  edges: support / attack
  atoms: pred(args)
        │
        ├─────────────► AF projection (args, attacks)
        │                 ► run semantics in Clingo (grounded / preferred / stable)
        │
        └─────────────► FOL export (TPTP)
                          ► run E‑prover to check entailment/consistency
        │
        ▼
   Diagnosis (detectors)
        │
        ▼
   Repair generation
   - AF enforcement (minimize edits)
   - FOL abduction (add minimal premise)
        │
        ▼
   Verification (Clingo/E‑prover)
        │
        ▼
   Report (Issue cards + patches)
```

---

# 1) The Strict IR (your core data model)

**Where to look:** `argir/core/model.py` (or equivalent `types.py`) + `argir.json` outputs.

### Core objects

* **Node (argument unit):**

  * `Premise` (often just a fact/statement with atoms)
  * `InferenceStep` (premises + optional rule ⇒ conclusion)
  * `Claim/Conclusion` (in many codebases, the conclusion lives on the inference node; some variants have explicit claim nodes)
  * Each node can carry **atoms** (e.g., `wet(street)`), and possibly `text` or `span` from NL.

* **Edge (relation):**

  * `support(source → target)`
  * `attack(source → target)` — includes `attack_kind` metadata (e.g., `contradiction`, `rebut`).

* **Atoms / Terms:**

  * `Atom(pred="wet", args=[Const("street")])`
  * Terms can be constants or (less often in practice) variables.

* **Metadata:**

  * `atom_lexicon`: known predicates/arity and constants the system may use.
  * optional `goal_id` hint (which node to focus on).

> **Limitation — “soft extraction” noise:**
> The soft pass sometimes creates **implicit rule nodes** (e.g., `IR_P1`) without real content. These can complicate structure and create spurious cycles. Recent branches either collapse them in AF projection or avoid producing them.

---

# 2) AF Projection & Semantics (Clingo)

**Why:** Abstract away content to a directed graph of **arguments** and **attacks** so we can ask a solver: “Is the goal accepted?”

### AF basics in code

* **AF facts:**
  `arg(a). arg(b). ...`
  `att(a,b).` means “a attacks b”.
* **Semantics (implemented as ASP encodings / helper library):**

  * **Grounded**: skeptical, conservative (often empty when there’s mutual attack).
  * **Preferred**: maximal admissible sets (credulous acceptance = “in at least one preferred extension”).
  * **Stable**: strong notion (may not exist).

### Enforcement (repair) idea

Given an AF and a **goal** node `G`, we can ask Clingo to pick **minimal edits** (e.g., add `att(x, y)` or delete a non‑hard attack) so that `G` becomes **accepted** under a chosen semantics. Edits are optimized with `#minimize` (and sometimes with a secondary `#maximize` to prefer larger extensions when approximating preferred).

**Artifacts:**

* `af_enforce.lp` — enforcement skeleton (edits + optimization); semantics appended at runtime.
* `af_enforce.py` — builds candidate edit sets, calls Clingo, parses edits into a **Patch**.

> **Limitations — semantics & candidates:**
>
> * **Grounded vs Preferred:** Grounded is very cautious; in `A ↔ B` both can be rejected, making repairs “invisible”. Preferred (credulous) is more constructive for repairs.
> * **Candidate pool breadth:** If you allow “any node attacks any attacker,” you may get weird but valid fixes. Most branches now **narrow** candidates to `goal → attackers(goal)` (and an optional abstract **defender** node), with a flag to widen if needed.
> * **Hard edges:** Contradictions / explicit negations are often marked **non‑deletable**. That’s principled, but repairs must then come from **adding** counter‑attacks or defenders.

---

# 3) FOL Export & Proofs (E‑prover)

**Why:** Some issues are **content** problems (“premises don’t entail the conclusion”). We export the IR to **TPTP FOF** and ask **E‑prover** to check entailment.

### TPTP problem shape

* **Axioms:** facts + rule encodings (depending on your exporter)
* **Conjecture:** the target conclusion (what we want to prove)
* Optionally, newly proposed **hypotheses** (abduced premises) are added as additional **axioms**.

E‑prover returns an SZS status like `Theorem`/`Unsatisfiable` (good), `CounterSatisfiable`, or times out.

> **Limitations — exporter coverage:**
> If the exporter only dumps **conclusions** but not **rules/backing**, E‑prover has nothing to *reason with*—it can only prove the conjecture if the hypothesis is essentially the conjecture itself. Newer branches wire the **official exporter** that includes rules/defeaters when available.

---

# 4) Diagnosis (what “issues” we detect)

**Where:** `argir/diagnostics.py`

### Built‑in detectors

1. **Unsupported inference**
   Premises + rule (if any) do **not** entail the conclusion.
   Signals: E‑prover cannot prove; AF rejects the node.

2. **Circular support**
   A node’s acceptance depends (transitively) on itself through support/derivation cycles.

3. **Contradiction unresolved**
   Two accepted (or key) nodes clash (explicit contradiction or strong rebut) with no resolution.

4. **Weak scheme instantiation**
   A recognized argumentation scheme (authority, causal, analogy, …) has unsatisfied **critical questions** (missing backing, scope, confounders).

5. **Goal unreachable**
   The goal is **not credulously accepted** under the chosen semantics.

Each detector emits an `Issue` with: `type`, `target_node_ids`, `evidence`, `detector_name`.

> **Limitations — detector truthiness:**
>
> * **Unsupported inference** can be raised either because content is missing (true gap) or because the **exporter omitted rules** (false positive).
> * **Goal unreachable** depends on semantics; under grounded, mutual attacks often make the goal “not accepted,” but that’s a modeling choice, not necessarily a flaw.

---

# 5) Repair generation (two engines)

## 5.1 AF enforcement (structural repairs)

**Goal:** minimally change the **attack graph** so the goal becomes accepted.

* **Edit types**:

  * `add_att(x, attacker_of_goal)` — “counter‑attack”
  * `use_defender` + `add_att(def, attacker)` — “introduce an abstract defender”
  * `del_att(x, y)` — remove an attack (**often blocked** for hard edges)
* **Optimization:** `#minimize` counts edits; optional `#maximize { in(X) }` biases toward preferred-like sets.
* **Verification:** Re‑run semantics on the patched AF; record optimality (“OPTIMUM FOUND”).

> **Limitations — principled but narrow:**
> AF enforcement cannot **invent content**. It can only re‑wire attacks. If the real issue is “missing premise,” AF may suggest adding a counter‑attack that is structurally valid but **content‑opaque**. That’s why AF enforcement is best for **conflict management**, not missing support.

## 5.2 FOL abduction (content repairs)

**Goal:** add **minimal premise(s)** (1–2 atoms) that make the conclusion **provable**.

* **Candidate generation:**

  * Use **predicates/arity** and **constants** already seen in the graph (and lexicon).
  * Prefer atoms that **share constants** with the target conclusion (“anchored”).
  * Deterministic order: 1‑atom first, then small 2‑atom combos.

* **Verification:**

  * Build the **TPTP** problem with your official exporter (axioms + conjecture).
  * Add hypothesis atoms as **axioms** and call **E‑prover** with a **short timeout**.
  * **Consistency guard:** also try to prove `$false`; if it’s provable, **reject** the hypothesis.

* **Patch:**

  * Add a **Premise** node with those atoms.
  * Add a **support** edge to the target inference.
  * (Optional) Recompute AF acceptance after the patch; include both AF and FOL results in the card.

> **Limitations — proof availability:**
>
> * Needs E‑prover installed to be fully trustworthy; otherwise you fall back to heuristics (clearly label as “unverified”).
> * If the exporter doesn’t include rules, only trivial abductions (e.g., “add exactly the claim”) will prove.
> * Even when provable, **plausibility** is not guaranteed—enforcing plausibility requires templates/schemes or typed domains.

---

# 6) The “Issue Card” (what shows in the UI / report)

Each card should include:

* **Issue**: type, short explanation, evidence (e.g., cycle path, conflicting atoms, failed CQs).
* **Minimal repair**:

  * **Patch JSON** (machine‑applyable): added nodes/edges or AF edits.
  * **Cost & optimality** (AF repairs): number of edits; “OPTIMUM FOUND”.
  * **Verification**:

    * AF semantics **before/after** and which semantics were used.
    * FOL status (E‑prover Theorem/Unsat) and **timing**.
* **Alternatives** (if there are ties; up to 3).

> **Limitation — expectation management:**
> For natural language inputs, many cards will say **“No automated repair available”**. That’s honest—most real arguments need **human judgment** for missing content. The card should explain *why* no edit was suggested (e.g., all edges are hard; E‑prover could not find a proof with ≤2 atoms; multiple contradictions).

---

# 7) CLI & Quick Recipes

Common runs:

```bash
# 1) Diagnose only (natural language input)
python -m argir.cli input.txt --out out --soft --diagnose

# 2) Diagnose + attempt repairs (grounded everywhere)
python -m argir.cli input.txt --out out --soft --diagnose --repair \
  --diagnostics-semantics grounded --repair-semantics grounded

# 3) Diagnose grounded, but repair under preferred (more constructive repairs)
python -m argir.cli input.txt --out out --soft --diagnose --repair \
  --diagnostics-semantics grounded --repair-semantics preferred

# 4) Focus on a known goal id (structured JSON)
python -m argir.cli argir.json --out out --diagnose --repair --goal C1

# 5) Demo-friendly toggles (if available in your branch)
python -m argir.cli input.txt --out out --soft --diagnose --repair \
  --repair-friendly-mode
```

**Outputs to inspect:**

* `out/report.md` — read the Issue Cards.
* `out/issues.json`, `out/repairs.json` — for programmatic analysis.
* Clingo/E‑prover logs in the verification artifacts (useful for debugging).

> **Limitation — “preferred” variance by branch:**
> Some branches had an **over‑simplified preferred encoding**. Newer updates reuse a single semantics source (admissible + `#maximize`) and enforce **credulous** acceptance. If repairs don’t show up under preferred, revert to grounded or check your semantics include/wiring.

---

# 8) Testing & Reproducibility

### Unit tests

* **Detectors**: craft tiny graphs (JSON fixtures) to trigger each issue type.

* **AF enforcement**:

  * Tiny AF with `att(A,G)` only → expect `add_att(G,A)` (cost = 1).
  * Odd cycle → expect `use_defender` + one attack (cost = 1–2).

* **FOL abduction**:

  * Rule: `raining → wet`; goal: `wet(street)` → expect hypothesis `raining(street)` or a 0‑ary `raining` depending on your signature.

### Property tests (high value)

* **Minimality** (small AFs): brute‑force edit sets of size ≤ K and assert the solver’s cost equals the true minimum.
* **Idempotence**: after applying a chosen repair, re‑diagnose; the same issue should not reappear.
* **Determinism**: run abduction twice with the same input; the top‑3 hypotheses must match.

> **Limitation — solver nondeterminism:**
> Clingo is deterministic given the same facts, but different **candidate pool orders** can change the first optimum model printed. Always **sort** facts and candidates you emit to ASP. For abduction, **sort predicates/constants** and **anchor** to target constants.

---

# 9) Troubleshooting Guide

**“No automated repair available” (common)**

* Check semantics: grounded can be too strict; try repair under preferred.
* Hard edges: if all attackers of the goal are **hard**, and you disallow additions, nothing can change. Allow `add_att(goal, attacker)` or enable a single **defender**.
* Abduction: if E‑prover is missing (or exporter omitted rules), most content repairs will fail. Install E‑prover and ensure your exporter emits rules.

**“Preferred repair didn’t ensure acceptance”**

* Make sure the ASP program includes **credulous acceptance**: `:- goal(G), not in(G).`
* For preferred: use **admissible** encoding + `#maximize { in(X) }` or a correct preferred encoding, and ensure you check **credulous** membership (exists an extension), not skeptical.

**“Repairs look weird (unrelated node attacks attacker)”**

* Your **candidate pool** is too broad. Restrict to `goal → attackers(goal)` and an optional defender, add a CLI flag to widen only if needed.

**“FOL abduction crashes or times out”**

* Lower `max_atoms` to 1 and reduce constants.
* Increase E‑prover timeout slightly (e.g., 2→3s) only for demonstration; keep default low.

---

# 10) How this differs from the older **Argument Debugger**

* The older repo combined LLM extraction with ASP reasoning and hand‑crafted repairs.
* **ARGIR** formalizes a **strict IR**, provides **AF and FOL exports**, and adds a **principled** diagnosis/repair layer with **verification**.
* You can port **schemes & critical questions** from the older repo to ARGIR as **detectors**; but **repairs** in ARGIR are now **verified** (Clingo/E‑prover), not only suggested.

---

# 11) A minimal end‑to‑end example (that always works)

### Text

> “If it rains, streets get wet. Therefore, the street is wet.”

### Expected pipeline behavior

* **Soft → Strict IR:** one inference node `C1` with rule `raining(x) → wet(x)`, missing premise `raining(street)`.
* **Diagnosis:** `unsupported_inference` for `C1`.
* **Repair (FOL abduction):** propose `raining(street)` (1 atom).

  * **E‑prover:** Theorem in \~0.1–1.0s (depending on setup).
  * **Patch:** add premise node with `raining(street)`; support it into `C1`.
* **Report:** Issue Card shows FOL entailed ✅; AF grounded acceptance likely improves ✅.

---

# 12) Hard limitations to keep in mind

* **Natural language is messy.** Even with a clean IR, many real claims require **judgment** or **external evidence**—automated repairs will be sparse. The UI must normalize “No automated repair” as a common, honest outcome.
* **Preferred semantics is a modeling choice.** It’s excellent for constructive repairs, but different encodings exist. Be explicit about **credulous vs skeptical** acceptance and document the semantics used on each card.
* **Hard edges reduce edit space.** Marking contradictions as non‑deletable is principled, but it forces the solver to **add** defenses rather than simplify. Provide a *demo‑only* toggle if you must show deletions.
* **E‑prover is the backbone for content repairs.** Without it (or without rules in your exporter), abduction becomes a heuristic. Always label verification status clearly.

---

## Quick “what to focus on next” (if you want a short roadmap)

* **Abduction polish (high ROI):** deterministic enumeration + consistency guard + exporter‑backed proofs (many branches already have some or all of this—consolidate into one file).
* **Candidate pool discipline:** default narrow (`goal→attackers`, one optional defender), with a `--widen` flag.
* **Report artifacts:** always show semantics used, cost/optimality, and E‑prover status.

---

If you want, I can tailor this doc into your repository as `docs/ARCHITECTURE.md` and add small “Limitations” callouts inline where your code is today (e.g., next to abduction, enforcement, exporter).
