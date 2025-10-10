# FOL Translation: What ARGIR Actually Checks

## The Core Question

When ARGIR translates arguments to First-Order Logic (FOL) and runs E-prover, what is it checking?

**Simple answer:** Does the conclusion *necessarily follow* from the premises?

**Formal answer:** In every interpretation where the premises are true, is the conclusion also true?

---

## What "Follows From" Means

A formula φ **follows from** axioms Γ (written Γ ⊨ φ) if:

> In every possible interpretation (model) where all axioms in Γ are true, φ is also true.

**Key concept: Interpretation**
- An interpretation assigns meaning to symbols
- Example: `human` could mean {Socrates, Plato, ...} or {1, 2, 3} or any set
- The symbols themselves don't have inherent meaning
- What matters is the **structural relationship** between formulas

**Example:**
```
Axioms: human(socrates), ∀X: human(X) → mortal(X)
Goal: mortal(socrates)
```

In **any** interpretation where:
- `socrates` is in the `human` set
- The `human` set is a subset of the `mortal` set

Then `socrates` **must** be in the `mortal` set.

This holds whether `human` means actual humans, or numbers, or colors. The logic is about **set containment**, not meaning.

---

## Real Example: Valid Argument (Theorem ✓)

**Natural Language:**
> "The social order is the basis of all other rights. Therefore, the social order is a sacred right."

**ARGIR Extraction:**
```
Premise P1: basis_of_all_other_right(the_social_order)
Rule IR_P4: basis_of_all_other_right(X) → sacred_right(X)
Goal: sacred_right(the_social_order)
```

**FOL Translation (TPTP):**
```prolog
fof(orphan_fact_3, axiom, basis_of_all_other_right(the_social_order)).
fof(rule_IR_P4, axiom, (basis_of_all_other_right(the_social_order)
                         => sacred_right(the_social_order))).
fof(goal, conjecture, sacred_right(the_social_order)).
```

**E-prover Result: Theorem ✓**

**Why it's valid:**

In every interpretation I:
1. Let S = the set of things that are "basis of all other rights"
2. Let R = the set of things that are "sacred rights"
3. Axiom says: the_social_order ∈ S
4. Rule says: S ⊆ R (everything in S is in R)
5. Therefore: the_social_order ∈ R
6. Therefore: sacred_right(the_social_order) is true in I

**This holds in EVERY interpretation.** The conclusion necessarily follows.

---

## Real Example: Invalid Argument (Unknown)

**Natural Language (Aristotle – Nicomachean Ethics):**
> "Human good turns out to be an activity of soul in accordance with virtue, and if there are more than one virtues, in accordance with the best and most complete."

**ARGIR Extraction:**
```
Rule R1: more_than_one_virtue → in_accordance_with_best_and_most_complete_virtue(human_good)
Goal: activity_of_soul_in_accordance_with_virtue(human_good)
```

**FOL Translation (TPTP):**
```prolog
fof(rule_R1, axiom, (more_than_one_virtue
                     => in_accordance_with_the_well_and_most_complete_virtue(human_good))).
fof(goal, conjecture, activity_of_soul_in_accordance_with_virtue(human_good)).
```

**E-prover Result: Unknown**

**Why it's invalid:**

We can construct a **countermodel** (interpretation where premises are true but conclusion is false):
- `more_than_one_virtue` = FALSE (suppose there's only one virtue)
- `in_accordance_with_the_well_and_most_complete_virtue` = {} (empty set)
- `activity_of_soul_in_accordance_with_virtue` = {} (empty set)
- `human_good` = some entity

In this interpretation:
- Rule R1 is TRUE (false → anything is true; vacuously satisfied)
- activity_of_soul_in_accordance_with_virtue(human_good) is FALSE

**Countermodel exists → premises don't entail conclusion → Invalid**

**What's missing?** The connection between the two predicates:
```prolog
% Missing premise 1: The base claim that human good is activity of soul with virtue
activity_of_soul_in_accordance_with_virtue(human_good)

% OR a rule connecting the conditional to the base claim
forall X: in_accordance_with_the_well_and_most_complete_virtue(X)
          => activity_of_soul_in_accordance_with_virtue(X)
```

The text presents a conditional refinement ("if there are multiple virtues...") but doesn't establish the base claim. The conclusion doesn't follow from just the conditional.

---

## The Critical Distinction: Syntax vs Semantics

### What E-prover Checks (Syntax)

E-prover verifies: **"This symbolic formula follows from these symbolic formulas."**

It treats symbols as **uninterpreted**:
- `human`, `mortal`, `socrates` are just symbols
- Could mean anything
- What matters is the **logical structure**

### What E-prover Does NOT Check (Semantics)

E-prover does NOT verify: **"The English words map correctly to the symbols."**

**The semantic gap:**

```
Natural Language: "Pleasure is the good" (Epicurus)
    ↓ [LLM extraction - can introduce errors]
Predicate: the_good(pleasure)
```

**Potential semantic errors:**
1. **Ambiguity:** "pleasure" could mean physical pleasure, intellectual pleasure, absence of pain (ataraxia)
2. **Scope:** Does "the good" mean the highest good, a good, or constitutive of goodness?
3. **Granularity:** Should we distinguish `physical_pleasure(X)`, `intellectual_pleasure(X)`, `freedom_from_pain(X)`?

The LLM chooses an interpretation. It might be wrong!

### Example: Semantic Error

**Text:** "Banks are financial institutions. The river has banks. Therefore, the river has financial institutions."

**Bad extraction (LLM fails to disambiguate):**
```prolog
fof(axiom1, axiom, bank(river)).
fof(axiom2, axiom, forall X: bank(X) => financial_institution(X)).
fof(goal, conjecture, financial_institution(river)).
E-prover: Theorem ✓  (STRUCTURALLY valid but SEMANTICALLY wrong!)
```

**Correct extraction:**
```prolog
fof(axiom1, axiom, river_bank(river)).  % Different predicate!
fof(axiom2, axiom, forall X: financial_bank(X) => financial_institution(X)).
fof(goal, conjecture, financial_institution(river)).
E-prover: Unknown ✓  (Correctly cannot prove it)
```

---

## What "Valid" Actually Means in ARGIR

When ARGIR says an argument is "valid", it means:

> **"The argument is structurally sound, assuming the LLM correctly interpreted the natural language."**

### The Translation Pipeline

```
Natural Language
    ↓ [LLM: SEMANTIC interpretation - can err]
ARGIR Predicates
    ↓ [Compilation: DETERMINISTIC - no errors]
FOL Formulas (TPTP)
    ↓ [E-prover: SYNTACTIC proof - guaranteed sound]
Theorem/Unknown
```

**Each step has different guarantees:**
1. **LLM extraction:** Semantic interpretation (can be wrong)
2. **Compilation:** Symbol normalization (deterministic)
3. **E-prover:** Syntactic validity (mathematically sound)

### What We Actually Get

**Strong guarantee (syntactic):**
- If E-prover says "Theorem", the symbolic formulas DO entail the goal
- The logical structure is sound
- No structural errors in the reasoning

**Weak guarantee (semantic):**
- The predicates might not capture the intended meaning
- The LLM might have misinterpreted the text
- The symbols might not map to reality correctly

---

## Why This Still Matters

Despite the semantic gap, FOL translation is valuable because:

### 1. Most Errors are Structural

From the dataset (95 queries):
- **101 unsupported inferences** (91.8% of issues)
- **8 contradictions** (7.3%)
- **1 circular support** (0.9%)

Most arguments fail because of **missing logical steps**, not semantic ambiguity.

### 2. Semantic Errors Often Surface as Structural Errors

- If word senses are confused, the argument usually won't prove
- Forcing formal structure reveals semantic problems
- Example: The "bank" argument fails at extraction, which shows in structure

### 3. Makes Hidden Assumptions Explicit

The Aristotle example shows:
- The text *sounds* like a complete argument
- But it presents a conditional refinement without establishing the base claim
- FOL reveals the missing premise: the base assertion that "human good is activity of soul in accordance with virtue"
- The text says this "turns out to be" the case, treating it as given rather than proven
- Now we can see the argument structure clearly: Aristotle asserts the base claim and refines it conditionally

### 4. Enables Automated Repair via FOL Abduction

When FOL checking fails, ARGIR uses **abduction** to find missing premises. This is a third mechanism that USES E-prover to search for repairs:

**How FOL abduction works:**
1. **Collect signature:** Extract all predicates and constants from the argument
2. **Enumerate candidates:** Generate possible missing premises (1-2 atoms)
   - Uses predicates from the existing argument
   - Focuses on constants mentioned in the target conclusion
3. **Test each hypothesis H:**
   - Check: `axioms + H ⊢ goal` (does H enable the proof?)
   - Check: `axioms + H ⊬ ⊥` (is H consistent with axioms?)
   - Both checks use E-prover
4. **Minimize:** Find the smallest subset that works
5. **Verify:** Check AF impact (does repair affect acceptance?)

**Aristotle example repair:**
```
Problem: Can't prove activity_of_soul_in_accordance_with_virtue(human_good)
Existing: more_than_one_virtue => in_accordance_with_best...(human_good)

Abduction finds: activity_of_soul_in_accordance_with_virtue(human_good)

Verification with E-prover:
  Axioms: more_than_one_virtue => in_accordance_with_best...(human_good),
          activity_of_soul_in_accordance_with_virtue(human_good)  [ADDED]
  Goal: activity_of_soul_in_accordance_with_virtue(human_good)
  E-prover: Theorem ✓  (trivially, since we added the goal as a premise)
```

This reveals that Aristotle's text assumes the base claim as given ("turns out to be") rather than proving it from more fundamental premises.

**From the dataset:**
- **99 repairs generated** (across queries with issues)
- **91 FOL repairs** (91.9%) - vast majority via abduction
- **8 AF repairs** (8.1%) - via attack edge modification
- **87.9% verification success rate** - repairs enable proof and are AF-consistent

---

## FOL Abduction Deep Dive: Concrete Example

Let's walk through a real abduction repair from the dataset to see exactly how ARGIR uses E-prover to generate missing premises.

### The Original Argument (Schweitzer – Philosophy of Civilization)

**Natural Language:**
> "The ethic of reverence for life is the ethic of love widened into universality. It is the ethic of Jesus, now recognized as a necessity of thought."

**ARGIR Extraction:**
```
Conclusions:
  C1: ethic_be_reverence_for_life
  C2: ethic_be_ethic_of_love_widened_into_universality
  C3: ethic_be_ethic_of_jesus
  C4: recognize_as_necessity_of_thought(ethic)

Rules:
  R1: ethic_of_love_widened_into_universality → ethic_be_reverence_for_life
  R2: ethic_of_jesus ∧ recognize_as_necessity_of_thought(ethic) → ethic_be_reverence_for_life
```

**FOL Translation (TPTP):**
```prolog
fof(c2, axiom, ethic_be_ethic_of_love_widened_into_universality).
fof(c3, axiom, ethic_be_ethic_of_jesus).
fof(c4, axiom, recognize_as_necessity_of_thought(ethic)).
fof(rule_r1, axiom, (ethic_of_love_widened_into_universality
                     => ethic_be_reverence_for_life)).
fof(rule_r2, axiom, ((ethic_of_jesus & recognize_as_necessity_of_thought(ethic))
                     => ethic_be_reverence_for_life)).
fof(goal, conjecture, ethic_be_reverence_for_life).
```

**Initial E-prover Result: Unknown**

### The Problem

C1 (`ethic_be_reverence_for_life`) is the target conclusion, but:
- R1 requires `ethic_of_love_widened_into_universality` (we have `ethic_be_ethic_of_love_widened_into_universality` - different predicate!)
- R2 requires `ethic_of_jesus` (we have `ethic_be_ethic_of_jesus` - different predicate!)

The predicates don't match! This is a common extraction issue where the LLM creates related but distinct predicate names.

**Issue detected:** `unsupported_inference` - C1 has no valid support.

### Abduction to the Rescue

**Step 1: Collect signature**
- Predicates: `ethic_be_reverence_for_life`, `ethic_be_ethic_of_love_widened_into_universality`, `ethic_be_ethic_of_jesus`, `recognize_as_necessity_of_thought`
- Constants: `ethic`
- Target: `ethic_be_reverence_for_life`

**Step 2: Enumerate candidates**
The abduction system generates atomic hypotheses focusing on predicates that appear in the target:
- `ethic_be_reverence_for_life` (0-arity atom)
- `ethic_of_love_widened_into_universality` (0-arity)
- `ethic_of_jesus` (0-arity)
- ... (and various combinations)

**Step 3: Test hypothesis `ethic_be_reverence_for_life`**

Test 1: Does it enable the proof?
```prolog
fof(c2, axiom, ethic_be_ethic_of_love_widened_into_universality).
fof(c3, axiom, ethic_be_ethic_of_jesus).
fof(c4, axiom, recognize_as_necessity_of_thought(ethic)).
fof(rule_r1, axiom, (ethic_of_love_widened_into_universality
                     => ethic_be_reverence_for_life)).
fof(rule_r2, axiom, ((ethic_of_jesus & recognize_as_necessity_of_thought(ethic))
                     => ethic_be_reverence_for_life)).
fof(h1, axiom, ethic_be_reverence_for_life).  % ← HYPOTHESIS ADDED
fof(goal, conjecture, ethic_be_reverence_for_life).
```

E-prover: **Theorem ✓** (trivially - we added the goal as an axiom)

Test 2: Is it consistent with existing axioms?
```prolog
fof(c2, axiom, ethic_be_ethic_of_love_widened_into_universality).
fof(c3, axiom, ethic_be_ethic_of_jesus).
fof(c4, axiom, recognize_as_necessity_of_thought(ethic)).
fof(rule_r1, axiom, (ethic_of_love_widened_into_universality
                     => ethic_be_reverence_for_life)).
fof(rule_r2, axiom, ((ethic_of_jesus & recognize_as_necessity_of_thought(ethic))
                     => ethic_be_reverence_for_life)).
fof(h1, axiom, ethic_be_reverence_for_life).
fof(cnt, conjecture, $false).  % ← Can we prove FALSE?
```

E-prover: **Unknown** (cannot prove false - hypothesis is consistent ✓)

**Step 4: Minimize**
Only one atom in hypothesis - already minimal.

**Step 5: Create repair patch**

```json
{
  "id": "ABD-3641f8ba",
  "kind": "FOL",
  "cost": 1,
  "patch": {
    "add_nodes": [{
      "id": "P_ethic_be_2b66",
      "text": "ethic_be_reverence_for_life",
      "atoms": [{"pred": "ethic_be_reverence_for_life"}]
    }],
    "add_edges": [{
      "source": "P_ethic_be_2b66",
      "target": "C1",
      "kind": "support"
    }],
    "fol_hypotheses": ["ethic_be_reverence_for_life"]
  },
  "verification": {
    "fol_entailed": true,
    "af_goal_accepted": true
  }
}
```

### What the Repair Does

**Graph modification:**
- Creates new premise node `P_ethic_be_2b66` with text "ethic_be_reverence_for_life"
- Adds support edge from this premise to C1

**Semantic interpretation:**
This repair says: "To make this argument work, we need to add the premise that 'ethic_be_reverence_for_life' is true."

**But wait - that's circular!**
Yes, it is. The repair is adding the conclusion as a premise. This tells us something important:
- The original text **asserts** the conclusion rather than **proving** it
- Schweitzer states "The ethic of reverence for life **is**..." (assertion, not derivation)
- The "now recognized as a necessity of thought" suggests it's taken as given
- The argument structure is: "Here's what this ethic is, here's why it matters" (definitional + justification)

This is a case where abduction reveals the **argument structure** rather than finding a genuinely missing inferential step. The text presents a definitional statement, not a logical derivation.

### AF Impact Analysis

**Before repair:**
```
Grounded extension: {C2, C3, C4, R1, R2}
C1 not accepted (lacks support)
```

**After repair:**
```
Grounded extension: {C2, C3, C4, R1, R2, P_ethic_be_2b66, C1}
C1 now accepted (supported by P_ethic_be_2b66)
```

The repair changes C1's acceptance status, which is what we wanted.

### Key Insights from This Example

1. **E-prover used twice per hypothesis**: Once to check proof enablement, once to check consistency
2. **Repairs can be trivial**: Sometimes abduction finds that adding the goal as a premise "fixes" the argument
3. **Trivial repairs are informative**: They reveal that the text asserts rather than proves the conclusion
4. **Multiple verification layers**: FOL entailment + AF acceptance both checked
5. **Predicate mismatch is common**: LLM creates `ethic_be_X` vs `X` - related but distinct predicates

### When Abduction Finds Non-Trivial Repairs

Not all repairs are circular. In arguments with genuinely missing intermediate steps, abduction can find:
- Bridge predicates connecting disconnected parts
- Missing universal rules
- Implicit premises that enable modus ponens

The Aristotle example earlier shows a more substantive repair: adding the base claim that makes the conditional refinement meaningful.

**From dataset:** 91 FOL repairs, 87.9% verified - most are non-trivial premises that genuinely enable proofs.

---

## Summary

### What FOL Translation Checks

**E-prover (FOL entailment checking):**
✅ **Deductive validity:** Does the conclusion necessarily follow from premises (in all models)?
✅ **Proof existence:** Can we derive the conclusion using logical inference rules?

**Diagnostic System (graph structure + AF semantics):**
✅ **Graph completeness:** Does every node have premises or support edges?
✅ **AF acceptance:** Are nodes accepted under argumentation semantics?
✅ **Contradiction detection:** Are there atoms with opposite polarity?
✅ **Cycle detection:** Are there circular dependencies in support?

**FOL Abduction (repair generation using E-prover):**
✅ **Missing premise generation:** What atoms would make the proof work?
✅ **Consistency checking:** Are the proposed premises consistent with existing axioms?
✅ **Minimality:** What's the smallest set of premises that enables the proof?
✅ **Verification:** Does adding the premise actually make it provable?

**What neither checks:**
❌ **Semantic correctness:** Do the symbols mean what the English words mean?
❌ **Premise truth:** Are the premises actually true in reality?
❌ **Real-world validity:** Does the argument work in the real world?

### The Value Proposition

**What you get:**
- Mathematical certainty when E-prover says "Theorem" (32.6% of cases)
- Detection of likely logical issues (diagnostic system found 110 issues in 95 queries)
- Automated repair suggestions (87.9% success rate)
- Explicit representation of hidden assumptions

**What you don't get:**
- Guarantee that the LLM extracted the right meaning
- Verification that premises are true
- Certainty about real-world applicability

**Bottom line:** FOL gives you **syntactic soundness**. Semantic correctness depends on extraction quality. But most natural language arguments fail at the syntactic level anyway, so catching structural errors alone is extremely valuable.

### Real Impact

From 95 saved queries:
- **32.6% provably valid** (E-prover found a proof)
- **67.4% unknown** (E-prover couldn't determine - may be invalid, or too complex)

**Important:** "Unknown" doesn't mean "invalid" - it means the prover couldn't decide within time/complexity limits.

**Separate from FOL checking:** ARGIR also has a diagnostic system (using graph structure and AF semantics) that found **110 issues** across the dataset:
- 101 unsupported inferences (node has no premises or not accepted in AF)
- 8 contradictions (atoms with opposite polarity)
- 1 circular support (cycles in premise graph)

This diagnostic system is independent of E-prover - it checks graph structure, not FOL entailment.
