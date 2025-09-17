# ARGIR Tutorial — From Text to Minimal, Verified Repairs

**Audience:** engineers, researchers, and analysts who want a fast way to turn natural‑language arguments into a structured graph, diagnose issues, and—when possible—apply **minimal, verified repairs**.

**What you’ll do in this tutorial**

1. Run ARGIR on an example input (no manual goal needed).
2. See how the **soft IR** makes the pipeline repair‑friendly.
3. Generate two kinds of repairs:

   * **Content repair** via **Abduction v2** (add a minimal premise proved by E‑prover).
   * **Structural repair** via **AF Enforcement** (add a minimal counter‑attack in the AF).
4. Read the report and understand verification (Clingo/E‑prover) and the run hash.
5. Know what to try when you see “No automated repair available”.

---

## What’s new in this hardened build

* **Soft IR (Repair‑Friendly)**

  * **Empty `IR_*` filtering:** implicit rule placeholders without atoms no longer become arguments in the AF (fewer spurious cycles).
  * **Conjunction splitting:** `P1 ∧ P2 → C` becomes separate supports (`P1 ⇒ C`, `P2 ⇒ C`), enabling “add exactly the missing antecedent”.
  * **Predicate canonicalization:** morphological/synonym variants normalized (e.g., rain/raining → `raining`), boosting proof/repair success.

* **Abduction v2 (Content Repairs)**

  * Deterministic hypothesis enumeration (sorted; **anchored to the goal’s constants**).
  * **E‑prover verification** with a **consistency guard** (rejects hypotheses that make `$false` provable).
  * **Hypothesis minimality:** removes redundant atoms (irredundant proofs).
  * Clean patches: one **Premise** node + **support** edge; AF acceptance re‑checked **after** patch.

* **AF Enforcement (Structural Repairs)**

  * **Preferred (credulous)** semantics for repair generation (constructive on mutual attacks).
  * **Targeted candidate pools:** focus on **goal → attackers(goal)** (+ optional defender), not “everyone attacks everyone”.
  * **Hard‑edge protection:** contradictions/negations preserved by default (no deletion “cheats”).

* **Hardening & Ops**

  * **TPTP sanitization** + **preflight validation** (zero syntax errors to E‑prover).
  * **Auto goal detection** (no `--goal` required in common cases).
  * **Run hash** in the report for reproducible CI.

---

## Prerequisites

* Python 3.8+
* **Clingo** (for AF semantics & enforcement)
* **E‑prover** (recommended) for FOL proofs; abduction works in “unverified” mode without it, but verified repairs require E‑prover.

> **Tip:** If E‑prover is absent or misconfigured, the system will label abduction results as **unverified** (or skip them), and the preflight step will show the reason.

---

## Quickstart: one command

```bash
python -m argir.cli examples/test_repair.json \
  --diagnose --repair --semantics preferred --repair-friendly
```

What this does:

1. Builds a **soft IR** from the input (repair‑friendly mode on).
2. Compiles a **strict IR** (validated graph + atoms).
3. Projects to an **AF** (arguments & attacks) and exports **FOL** (TPTP).
4. **Diagnoses** issues.
5. Attempts **repairs**:

   * AF enforcement (preferred, credulous) with targeted candidates.
   * Abduction v2 (1–2 atoms), proved by E‑prover with consistency guard.
6. Writes a report (`report.md`) with **Issue Cards** and **repairs.json** with machine‑readable patches.
7. Prints a **run hash** at the top of the report for reproducibility.

---

## Core concepts (5 minutes)

* **Soft IR** — flexible extraction from NL. Now shaped for repairability:

  * Filters empty `IR_*` nodes from the AF.
  * Splits conjunctions so “missing one antecedent” is a natural repair.
  * Canonicalizes predicate names to match rules.

* **Strict IR** — analyzable graph (Premise / InferenceStep nodes, support/attack edges, atoms `pred(args)`).

* **AF (Abstract Argumentation Framework)** — abstract graph of **arg/att** used by Clingo to compute acceptability under **grounded / preferred / stable** semantics.

* **FOL (TPTP/FOF)** — first‑order formulas exported from the strict IR for **E‑prover**.

* **Issue** — a diagnosed problem (unsupported inference, circular support, contradiction, goal unreachable, weak scheme).

* **Repair** — a minimal change, verified:

  * **AF repair**: counter‑attack/defender (structural).
  * **FOL repair** (abduction): add 1–2 premise atoms that **prove** the conclusion.

---

## Step‑by‑step walkthrough

### 1) Ingest & extract (Soft IR)

With `--repair-friendly`:

* Empty `IR_*` placeholders **do not** become AF arguments.
* Conjunctions become multiple supports.
* Predicates are normalized (e.g., `rain` → `raining`).

> **Limitation:** Soft IR is still heuristic. If extraction never finds rule‑like structure, abduction must rely on domain facts already present (it won’t invent “world knowledge”).

### 2) Compile to Strict IR

The strict IR ensures:

* Nodes/edges are well‑formed.
* Atoms have canonical predicates & arities.
* `metadata.atom_lexicon` is populated (abduction chooses hypotheses from here).

### 3) Diagnose

Detectors flag issues even if no repair will exist (e.g., grounded semantics might reject everyone in a mutual attack). Typical findings:

* **Unsupported inference** (common for missing premises).
* **Circular support**.
* **Contradiction unresolved**.
* **Goal unreachable** (under the selected semantics).
* **Weak scheme instantiation** (critical questions unmet).

### 4) Generate repairs

**AF Enforcement (structural)**

* Semantics: **preferred (credulous)** for repair generation (more constructive).
* Candidates: by default, **goal → attackers(goal)** (+ optional defender).
* Optimization: **minimize** edits; show **OPTIMUM FOUND** when successful.

**Abduction v2 (content)**

* Enumerates 1‑atom (then 2‑atom) **deterministically**, anchored to the goal’s constants.
* Uses **E‑prover** to prove the target; then checks **consistency** (rejects if `$false` becomes provable).
* Shrinks multi‑atom hypotheses to **irredundant** sets.
* Builds a patch: add a **Premise** node with those atoms + **support** to the inference; re‑checks AF acceptance **after** patch.

> **Limitation:** If your FOL export lacks rules linking premises to conclusions, only trivial abductions will prove (e.g., hypothesize the claim itself). The exporter now includes rules when they exist.

### 5) Verify & record

* AF repairs: Clingo returns the model; report includes **edit cost** and **OPTIMUM FOUND**.
* Abduction repairs: report includes **SZS status** (Theorem/Unsat), **proof time (ms)**, and the exact hypothesis atoms.
* The top of the report shows a **run hash** (strict IR + settings) for reproducible comparisons.

---

## Reading an Issue Card (example)

```markdown
### Issue I-003 — Unsupported inference (C1)
**Why:** Premises do not entail the conclusion under exported rules (E‑prover failed); C1 rejected in grounded.

**Minimal repair (verified):** Add premise `raining(street)`
- Patch: add Premise P_hyp_42 with atom `raining(street)`; add support P_hyp_42 → C1
- FOL: **entailed ✅** (E‑prover 120 ms)
- AF after patch (grounded): **accepted ✅**
- Notes: Hypothesis is **irredundant** (1 atom)

**Alternatives (same cost):** none found
```

**Where to look in files**

* Human: `report.md` (Issue Cards)
* Machine: `repairs.json` (patch objects; useful for applying edits or metrics)

---

## Guided examples (use the provided fixtures)

### A) Missing premise → Abduction v2

```bash
python -m argir.cli examples/test_repair.json \
  --diagnose --repair --semantics preferred --repair-friendly
```

Expect:

* Issue: **Unsupported inference**
* Repair: **Add premise** (1 atom), E‑prover proves; AF acceptance after patch ✅

### B) Mutual attack → AF Enforcement

```bash
python -m argir.cli examples/mutual_attack.json \
  --diagnose --repair --semantics preferred --repair-friendly
```

Expect:

* Issue: **Goal unreachable (preferred, credulous)**
* Repair: **Add counter‑attack** `GOAL → ATTACKER` (cost=1, **OPTIMUM FOUND**)

### C) Honest “No automated repair”

```bash
python -m argir.cli examples/no_repair.json \
  --diagnose --repair --semantics preferred --repair-friendly
```

Expect:

* Issues flagged; card explains **why** no repair could be generated (e.g., all edges hard; no provable hypotheses ≤2 atoms).

---

## Reproducibility & CI

* **Run hash** appears at the top of `report.md` and in logs. If the hash matches, outputs are byte‑stable (given same environment).
* Determinism is enforced by:

  * Sorted predicates/constants in abduction.
  * Anchoring to goal constants first.
  * Stable candidate pools for AF.

---

## Troubleshooting (checklist)

1. **No goal detected**
   Auto detection failed on this input—pass `--goal <NODE_ID>` or label one in metadata.

2. **No abduction repairs**

   * Ensure E‑prover is installed and preflight passes.
   * Check that the FOL export includes rules linking premises to the conclusion.
   * Raise `--abduce-timeout` slightly (e.g., 2.0 → 3.0) for hard proofs.

3. **No AF repairs**

   * Verify you’re running repairs under **preferred** semantics.
   * Confirm candidate pool includes **goal → attackers(goal)** or enable the optional defender.
   * If all relevant attacks are **hard** and additions are disabled, no structural fix exists—this is expected.

4. **Weird predicate names in TPTP**
   The sanitizer will quote/sanitize invalid tokens; prefer canonical predicates (repair‑friendly extraction already helps).

---

## FAQ

**Q: Why do I see issues but no repairs?**
Because the system won’t invent world knowledge or delete contradictions by default. If there’s no small, provable premise or a clean AF edit, it reports “No automated repair” and explains why.

**Q: Why preferred semantics for repair?**
Preferred (credulous) enables constructive fixes in mutual‑attack motifs where grounded is empty. The card labels which semantics were used.

**Q: Does abduction change the model?**
Yes—by adding a new **Premise** node with 1–2 atoms. We verify the effect by proving the target (E‑prover) and checking AF acceptance after the patch.

---

## Appendix A — Sample patch (machine‑readable)

```json
{
  "add_nodes": [
    {
      "id": "P_hyp_42",
      "kind": "Premise",
      "atoms": [{"pred":"raining","args":["street"]}],
      "text": "raining(street)",
      "rationale": "Added by abduction to support inference"
    }
  ],
  "add_edges": [
    {"source":"P_hyp_42","target":"C1","kind":"support"}
  ],
  "del_edges": [],
  "fol_hypotheses": ["raining(street)"],
  "af_edits": []
}
```

---

## Appendix B — What’s still out of scope (by design)

* Inventing facts outside the seen predicate/constant lexicon.
* Deleting contradiction edges by default (you can toggle this internally for demos, but it’s off in production).
* Proving long, multi‑premise chains under very tight timeouts (raise `--abduce-timeout` for research runs).

---

### You’re done

You now have a hardened, **repair‑friendly** ARGIR that:

* **Diagnoses** issues reliably,
* **Proposes minimal, deterministic repairs** when they exist,
* **Proves** content fixes,
* **Verifies** structural fixes, and
* Gives you a **reproducible** audit trail via run hashes.

For deeper dives (API usage, patch application at scale), open the example fixtures and the `repairs.json` your run produced—everything you need is in there.
