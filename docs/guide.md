# ARGIR, Reframed: Soft IR → Strict IR → AF/FOL → Diagnosis → Repair

Think of ARGIR as two stacked layers:

1. **Soft IR (extraction layer)** — heuristic/LLM-ish structures directly from natural language. This layer is flexible and forgiving; it captures text spans, loosely typed predicates, tentative supports/attacks, and sometimes **implicit rule nodes** (often named `IR_*`).
2. **Strict IR (analysis layer)** — a cleaned, strongly typed graph built *from* the soft IR. It has explicit node kinds, canonical atoms, validated edges, and is safe to “compile” into:

   * an **AF** (Abstract Argumentation Framework) for solver‑based acceptance, and
   * **FOL** (TPTP/FOF) for theorem proving.

**Diagnosis** runs mostly on the strict IR (+ AF/FOL projections). **Repairs** try to modify either the AF structure (enforcement) or the strict content (abduction). The **soft IR** shapes what the strict IR looks like — and that is the #1 reason repairs feel finicky.

---

## 1) What the Soft IR is (and isn’t)

**Goal:** capture *what the author seems to argue* with minimal commitment to a formal theory.

### Typical soft‑IR constructs

* **Soft nodes**

  * “Statement‑like” units: sentences/clauses that *look like* premises or claims.
  * “Rule‑like” units: often created when a sentence contains cues like *if/then* or *because*. These are the `IR_*` nodes—**implicit rules** with weak structure.
* **Soft edges**

  * `support`: “X because Y”; “if P then C”; “since … therefore …”
  * `attack`: negation, contradiction, refutation, “but”, “however”
* **Soft atoms**

  * From shallow IE over spans: `pred(args)` with constants harvested from NER or tokens; types are guesses.
* **Metadata**

  * Span offsets, scheme hints (authority/causal/analogy), and a crude **atom lexicon** (seen predicates and constants).

### Why it exists

* NL is messy. The soft IR lets the system **not fail** just because it can’t fully parse a rule; instead it adds a proxy node (`IR_*`) and keeps going.
* It is the **main pipeline** for NL inputs: everything downstream depends on how well this layer approximates structure.

> **Limitations of soft IR (important):**
>
> * **Implicit rule nodes (`IR_*`) are often empty shells.** They have no atoms or only vague ones. If projected as *arguments*, they introduce cycles and mutual attacks that **don’t correspond to the author’s reasoning**.
> * **Conjunctions get lumped.** “P1 and P2 and P3 → C” may be represented as one multi‑premise step; repairs that want to “add just P2” can’t naturally target this.
> * **Predicate/constant drift.** The same thing can appear with multiple names (“crime\_rate”, “crime”), making provability and attack alignment fail later.
> * **Scheme tags are diagnostic, not proof.** A “causal” tag doesn’t give you an actual causal law the prover can use.

---

## 2) From Soft IR to Strict IR (the “lowering” step)

**Goal:** compile the flexible soft IR into a **validated strict graph** you can analyze.

### What the strict IR guarantees

* **Node kinds:**

  * `Premise` (facts or assumed statements)
  * `InferenceStep` (premises + optional rule ⇒ conclusion)
* **Edges:** `support` and `attack` with basic well‑formedness.
* **Atoms:** canonicalized `pred(args)` with consistent arity and argument order.
* **Lexicon:** the predicate set and constants that downstream tools may use.

### What happens to `IR_*` here?

* Best case: softened rules become **explicit** rule applications inside `InferenceStep`s (e.g., a rule schema with antecedents).
* Common case: if there isn’t enough structure, `IR_*` remains an **intermediate** node that connects a premise‑ish text to a conclusion‑ish text.

> **Limitations of the lowering step:**
>
> * If `IR_*` survives to strict IR as a **node**, your AF will later have **extra arguments** with unclear content.
> * If antecedents are grouped into one big “premises” bag, abduction can’t target the *one* missing antecedent; it must fabricate an entire premise node with unspecified relation to the rule.
> * If canonicalization changes predicate names (e.g., “rain” vs “raining”), a perfectly sensible abduced fact won’t match the rule head used for proving.

---

## 3) Projections: AF and FOL

### AF (Abstract Argumentation Framework)

* **What we build:**

  * `arg(X)` for strict nodes that act as arguments (often `InferenceStep` or `Premise`).
  * `att(A,B)` when A contradicts B (either because of explicit negation or a learned rebut policy).
* **Semantics:**

  * **Grounded** (skeptical; conservative)
  * **Preferred** (credulous; larger admissible sets)
  * **Stable** (strong; may not exist)
* **Enforcement (repairs):** Ask Clingo to choose minimal edits to make a **goal** node accepted.

> **AF limitations that block repairs:**
>
> * **Grounded is often empty** in mutual attacks (`A ↔ B`). Your “goal unreachable” detector may not fire or may provide no constructive move.
> * **Hard edges.** If contradiction edges are flagged *non‑deletable*, and your candidate pool does **not** include *add‑attack* moves (or includes them too broadly), the solver either has **no solution** or returns **odd fixes**.
> * **`IR_*` as arguments.** If you project `IR_*` nodes as full arguments, you can create cycles/attacks that are artifacts, not real disagreements. Repairs try to fix those artifacts, not the actual content gap.

### FOL (First‑Order Logic, TPTP/FOF via exporter)

* **What we build:**

  * Axioms: facts + (when available) rules exported from strict IR.
  * Conjecture: the target conclusion (or sub‑claim) we want to prove.
* **Abduction (repairs):** We add 1–2 **hypothesis atoms** (as extra axioms) and ask **E‑prover** to prove the conjecture. If it succeeds—and remains **consistent**—we create a new **Premise** that supports the inference.

> **FOL limitations that block repairs:**
>
> * **Exporter without rules.** If the exporter doesn’t include usable rules, E‑prover can only prove the conjecture when the hypothesis is literally the conjecture itself—trivial and unhelpful.
> * **Predicate drift.** If the rule says `raining(x) → wet(x)` but the target concludes `wet_streets`, there’s no bridge rule; abduction can’t find a 1‑atom hypothesis that makes the proof.
> * **Timeouts.** A 1–2s prover cutoff is healthy for UX but means difficult proofs won’t appear as repairs.
> * **No types.** Hypothesis enumeration over a large, untyped lexicon produces many implausible candidates; after pruning you might simply not test the one that works.

---

## 4) Diagnosis (why you *see* issues even when you get **no repairs**)

Detectors do **not** require an available fix; they’re checking *properties*:

* **Unsupported inference:** “Premises don’t entail conclusion” (or no premises).
  ↳ True even when abduction can’t find a safe/short hypothesis.
* **Circular support:** “You depend on yourself.”
  ↳ True even if AF enforcement is restricted (e.g., hard edges only).
* **Contradiction unresolved:** “Two nodes clash without resolution.”
  ↳ True even if you forbid deleting the contradictory edge and don’t allow adding counter‑attacks.
* **Goal unreachable:** “Goal not accepted under chosen semantics.”
  ↳ True under grounded in many symmetric graphs; still no repair if the candidate pool is empty or only contains forbidden edits.

**So it’s entirely consistent to have: issues ✅, repairs ❌.** That’s not a bug; it’s a statement about **repairability** under your current constraints.

---

## 5) Repair engines (and their **preconditions**)

### 5.1 AF enforcement (structural)

**You get a repair only if ALL are true:**

1. **Goal is identifiable** (CLI `--goal` or auto‑detected).
2. **There exists a small edit set** (within your `max_af_edits`) that makes the goal **accepted** under the chosen semantics.
3. **Candidate pool is non‑empty** (e.g., at least `goal → attacker(goal)` allowed, or a **defender** is permitted).
4. **Hard‑edge policy allows a change** (if all relevant edges are “hard” and additions are disabled, no solution).
5. **Semantics is constructive** (preferred credulous is often needed for mutual‑attack motifs).

If any is false, you’ll see **no structural repair**.

### 5.2 FOL abduction (content)

**You get a repair only if ALL are true:**

1. **Exporter provides a bridge** from premises to the target (rules or facts the prover can use).
2. **Lexicon alignment**: the hypothesis predicates/arity/constants match what the rules expect.
3. **Search finds a working hypothesis** within your `max_atoms` and candidate budget.
4. **E‑prover can solve within timeout**.
5. **Consistency**: the hypothesis doesn’t make `$false` provable.

If any is false, you’ll see **no content repair**.

---

## 6) Why repairs have been “finnicky” in practice (root causes → fixes)

| Symptom                                        | Root cause in the pipeline                                                | What to do (minimal)                                                                                                                                                |
| ---------------------------------------------- | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Issues detected but **no repairs**             | AF: grounded semantics + mutual attacks; hard edges; empty candidate pool | For enforcement: use **preferred (credulous)** for repair; allow `goal→attackers` (and optionally a single **defender**); keep hard edges but **add**, don’t delete |
| Abduction **rarely** offers a fix              | Exporter lacks **rules**; predicate drift; E‑prover not installed         | Export FOL rules for inference steps; **canonicalize** predicates; install E‑prover; shorten search to **anchored** hypotheses                                      |
| Abduction offers **nonsense**                  | Lexicon too broad; no types                                               | Limit to **seen predicates/constants**; prefer constants appearing in the **target**; add light types when available                                                |
| Enforcement produces **weird** counter‑attacks | Candidate pool too broad (“anyone can attack anyone”)                     | Default to `goal→attackers` (+ defender), expose a `--widen` flag only if needed                                                                                    |
| AF full of **spurious cycles**                 | `IR_*` nodes projected as arguments                                       | In AF projection, **don’t create arg()** for empty `IR_*`; treat them as **edge warrants** (metadata)                                                               |
| **Unsupported inference** but no abduction fix | The gap is **world knowledge** or multi‑premise; proof too hard           | Increase `max_atoms` to 2; or create a **templated premise** via scheme tag (still verify with E‑prover)                                                            |

---

## 7) Soft‑IR–first: how to **shape** extraction to maximize repairs

1. **Prefer single‑step rules**: When parsing *if/then* sentences, map them to a single `InferenceStep` with **explicit antecedents**, not a chain of `IR_*` nodes.
2. **Split conjunctions**: Represent `P1 ∧ P2 → C` as **two** supports (`P1 ⇒ C` and `P2 ⇒ C`), or at least make `P1` and `P2` identifiable premises. This lets abduction add exactly the missing one.
3. **Canonicalize predicates early**: Decide that `raining` is the predicate, not `rain` or `is_rain`, and normalize consistently.
4. **Keep contradictions explicit**: Mark **what negates what** (those are good *attacks*), but don’t project `IR_*` as independent **arguments** in AF unless they carry atoms.
5. **Seed the lexicon**: Copy seen predicates and constants into `metadata.atom_lexicon`. Abduction relies on this to propose meaningful, provable hypotheses.
6. **Tag schemes (optional)**: If you detect “argument from authority” or “causal,” store that as soft metadata; abduction can use it to prioritize plausible hypotheses (still verified).

> **Limitation:** These are extraction policies, not logical truths. They will **bias** what repairs are possible. That’s intentional—your aim is a *repair‑friendly* strict IR.

---

## 8) A concrete, reproducible **debug playbook** when repairs don’t appear

1. **Is there a goal?**

   * If not passed on CLI, pick one with highest incoming `support`.
2. **AF quick scan**

   * Count attackers of goal; list which are **hard**.
   * If all attackers are hard and additions are disabled → no AF repair is possible.
3. **Try enforcement under preferred (credulous)**

   * If still no solution, print the **candidate pool**; if empty, enable `goal→attackers` and a **defender**.
4. **Exporter sanity**

   * Does the FOL axioms file contain any **rules** that can link premises to the goal? If not, abduction is limited.
5. **Abduction inputs**

   * Print the **predicate/arity** map and the **constants**. Do they match the goal’s head? If not, canonicalize.
6. **E‑prover path and timeout**

   * Verify E‑prover is called; try a 2–3s timeout for the test; read SZS status in the artifacts.

---

## 9) A tiny end‑to‑end example (designed to always yield a repair)

**Text:**
“If it rains, the street gets wet. Therefore, the street is wet.”

**Soft IR (what you want):**

* Premise‑like atom candidates: `raining(street)`, `wet(street)`
* One `InferenceStep` C1: antecedent pattern `raining(x) → wet(x)`; **no premise** attached for `raining(street)`
* No `IR_*` nodes projected as arguments

**Strict IR:**

* Node C1 with rule (`raining(x) → wet(x)`), conclusion `wet(street)`, **missing premise**
* No contradictions

**Diagnosis:** `unsupported_inference` on C1

**Repair (abduction):** Add **one** premise `raining(street)`

* **E‑prover** proves `wet(street)` under the exported rule
* **Patch:** add new Premise node with `raining(street)`, support edge to C1
* **AF:** grounded acceptance of C1 improves (optional check)

---

## 10) What to upgrade first if you want repairs to show up more

1. **Soft‑IR shaping** (extraction policy):

   * Don’t project empty `IR_*` as AF arguments; split conjunctions; canonicalize predicates.
2. **Abduction v2** (deterministic + exporter‑backed):

   * Use the official FOL exporter (include rules), anchor hypotheses to the goal’s constants, add a **consistency guard**.
3. **Enforcement defaults**:

   * Use **preferred (credulous)** for repair (keep grounded for display); allow `goal→attackers` and one **defender**; keep **hard edges non‑deletable**.

These three changes alone will convert a large chunk of “diagnosed but unrepaired” cases into **actionable, minimal, verified repairs**—without hand‑crafting strict JSON.

---

## 11) FAQ (short)

**Q: Why does diagnosis say “unsupported inference” if abduction can’t fix it?**
A: Because the check is correct: your current premises don’t entail the conclusion. Abduction fails when there’s no short, safe hypothesis the prover can use (missing rules, mismatched predicates, or too hard within the timeout).

**Q: Why not relax hard edges so AF repairs show up?**
A: You can, but then the solver will “fix” contradictions by deleting them, which is usually misleading. Better to **add** a defender/counter‑attack or fall back to human judgment.

**Q: Why does preferred semantics matter?**
A: It allows **credulous** acceptance in symmetric graphs where grounded is empty, enabling constructive AF repairs (especially counter‑attacks) without lying about sceptical status in the Diagnosis view.

---

### Bottom line

* The **soft IR is the main pipeline**: the shapes it creates **directly determine** whether AF enforcement and FOL abduction even have a chance.
* Repairs are “finnicky” not because the engines are wrong, but because **repairability has preconditions** (goal/semantics/candidates for AF; rules/lexicon/timeout for FOL) that natural language **rarely** satisfies out of the box.
* Make the soft IR **repair‑friendly** (simple rules, split conjunctions, canonicalization), and adopt **deterministic, exporter‑backed abduction** + **preferred‑based enforcement**. You’ll still show “No automated repair” often—that’s honest—but you’ll also get **clear, minimal, verified fixes** in the cases where automation should work.
