# The Argument Debugger: Mapping the Structure of Philosophical Reasoning

## The Vision

I set out to build a tool that would combine the semantic understanding of large language models with the precision of symbolic logic. The idea was straightforward: use an LLM to parse natural language arguments into formal representations, then verify them with theorem provers and argumentation solvers. Extract the structure, check the logic, find the gaps.

The hypothesis was that this hybrid approach—neural parsing plus symbolic verification—would reveal insights that neither component could provide alone. The LLM would handle the messy semantics of natural language; the logic tools would provide rigorous validation.

After building two prototypes and collecting 95 arguments (mostly classic philosophical texts, some everyday reasoning), I found something unexpected: the most valuable artifact wasn't the logical verification. It was the **map** itself—the intermediate graph representation that made argument structure visible.

## What the System Does

The Argument Debugger (the second prototype of which I call ARGIR—Argument Graph Intermediate Representation) processes a piece of argumentative text through several stages:

**1. Soft Extraction (LLM)**
The system prompts an LLM (Gemini) to extract argument structure in a permissive "Soft IR" format. The LLM identifies:
- Premises and conclusions
- Inference rules (if/then patterns)
- Support and attack relationships
- Quantifiers and variables

Example from Plotinus's *Enneads*:
```
"Never did eye see the sun unless it had first become sun-like,
and never can the soul have vision of the First Beauty unless
itself be beautiful."
```

The LLM extracts two parallel rules:
- R1: eye_see_sun(X) → eye_become_sun(X)
- R2: soul_have_vision(Y) → soul_be_beautiful(Y)

**2. Compilation (Deterministic)**
The soft extraction is compiled into strict ARGIR:
- Predicate canonicalization (lowercase, underscores)
- ID assignment (R1=rule, C1=conclusion, P1=premise)
- Implicit rule synthesis (if a node has premises+conclusion but no rule)
- Graph validation and auto-patching

**3. Dual Verification**
The compiled graph is checked two ways:

*Argumentation Framework (AF):*
- Projects graph to Dung's abstract argumentation
- Computes extensions (grounded/preferred/stable) with Clingo
- Checks which claims survive dialectical scrutiny

*First-Order Logic (FOL):*
- Translates to TPTP format
- Calls E-prover to attempt proof
- 32.6% of arguments (31/95) are provably valid
- But 61% of these (19/31) are *trivial*: the goal is also an axiom
- Only 12.6% (12/95) are *non-trivially* proved

**4. Diagnosis & Repair**
If issues are detected, the system generates repairs:
- FOL Abduction: Searches for missing premises (91.9% of repairs)
- AF Enforcement: Modifies attack edges to fix acceptance (8.1% of repairs)

From 95 queries, the system found:
- 110 issues (in 49 queries)
- 99 repairs (87.9% verified)
- Most common issue: unsupported inferences (91.8%)

## The Surprise: The Map Matters More Than the Logic

I expected the logical verification to be the payoff. Instead, I found that **the graph representation itself** was the most interesting output.

### What the Graph Reveals

Consider Schweitzer's *Philosophy of Civilization*:
```
"The ethic of reverence for life is the ethic of love widened
into universality. It is the ethic of Jesus, now recognized as
a necessity of thought."
```

The graph shows:
- C1: ethic_be_reverence_for_life [GOAL]
- C2: ethic_be_ethic_of_love_widened_into_universality
- R1: ethic_of_love... → ethic_be_reverence_for_life

But E-prover fails: predicate mismatch. R1 requires `ethic_of_love_widened_into_universality` but we have `ethic_be_ethic_of_love_widened_into_universality`. The LLM created syntactically distinct predicates for the same concept.

The abduction system "repairs" this by suggesting: add premise `ethic_be_reverence_for_life`. That's circular! But it's informative: Schweitzer **asserts** the conclusion, he doesn't **derive** it. The text is definitional, not inferential. The graph makes this visible.

### What Proved vs. Unproved Arguments Look Like

From the 95 queries, I analyzed what distinguishes the 32.6% that E-prover proved:

**Proved arguments have:**
- More explicit rules (avg 2.4 vs 1.5)
- Fewer standalone facts (avg 1.3 vs 1.9)
- Simpler structure (often just 2-3 rules, no edges)
- Clean conditional form: "if A then B"

**Example (Plotinus - trivial proof):**
The entire argument is two parallel rules. The goal is R2 itself. E-prover trivially proves it because the rule is both axiom and conjecture. The "proof" reveals structure, not validity.

Of the 31 proved arguments, **19 (61%) are trivial** like this: the goal appears as both axiom and conjecture. Only **12 (12.6% of total) are non-trivially proved**—where E-prover actually derives a conclusion from distinct premises via rules.

**Example (Rousseau - non-trivial proof):**
```
Premise: basis_of_all_other_right(the_social_order)
Rule: basis_of_all_other_right(X) → sacred_right(X)
Goal: sacred_right(the_social_order)
```
E-prover applies modus ponens to derive the conclusion. This is genuine derivation, not just axiom = conjecture.

**Unproved arguments have:**
- More asserted facts
- Predicate drift (LLM inconsistency)
- Missing intermediate steps
- Complex nested reasoning

The logic doesn't capture the interesting parts. Philosophical arguments are rich because of:
- Implicit cultural context (Epicurus's "pleasure" vs modern usage)
- Rhetorical force (Schopenhauer's pessimism isn't a syllogism)
- Conceptual innovation (Heidegger's "house of Being")

FOL sees: undefined predicates, missing rules, provability timeout.

## The Implementation: What Works and What Doesn't

### The Soft IR Pipeline (What Works)

The two-stage extraction was crucial:

**Stage 1 (Soft IR):** LLM produces permissive JSON
- No canonical predicates required
- Flexible IDs and references
- Simple predicate names (e.g., "raining", "suffer")

**Stage 2 (Compilation):** Deterministic processing
- Canonicalization via normalization (not LLM)
- ID assignment via graph topology
- Validation with auto-patching
- Implicit rule synthesis

This separation worked because:
- LLMs are good at structure, bad at consistency
- Deterministic code is good at normalization, bad at semantics
- Each does what it's suited for

Best-of-k sampling (try k=3 extractions, pick best) improved extraction quality significantly. Scoring criteria: fewer errors, more rules, cleaner predicates, proof success.

### The Semantic Parsing Problem (What Doesn't Work)

The fundamental issue: **you can't control LLM semantic interpretation**.

**Predicate drift:**
- Same concept, different predicates: `raining` vs `rain` vs `is_raining`
- FOL proofs fail when predicates don't match
- Canonicalization helps but doesn't solve it

**Quantifier scope:**
- "All life is suffering" - domain? All living things? All moments of life?
- LLM picks one interpretation
- Might be wrong, can't verify

**Polarity confusion:**
- When is negation explicit vs. implicit?
- "Individual will can never be satisfied" - is this `¬satisfy(will)` or `never_satisfy(will)`?
- LLM polarity repairs help but are heuristic

The core tension: formalization requires precision the LLM can't guarantee. The Soft IR helps by being permissive, but semantic correctness still depends on extraction quality.

### The Verification Machinery (Mixed Results)

**AF semantics (works well):**
- Grounded extension computation is fast (Clingo)
- Catches circular support (Schopenhauer: C1 → P1 → C1)
- Detects unresolved contradictions
- But: often too conservative (grounded can be empty)

**FOL proving (limited but real):**
- 32.6% theorem rate (31/95)
- Timeouts on complex arguments (2s default)
- Predicate mismatch is common blocker
- When it works, confirms structural validity

**Issue detection (highly effective):**
- Found 110 issues across 49/95 queries
- 91.8% unsupported inferences
- 7.3% contradictions
- 0.9% circular support

Surprisingly, philosophical texts are **internally consistent** but **formally incomplete**. They don't contradict themselves often; they just don't provide all the inferential steps.

### The Repair System (Informative Even When Trivial)

**FOL Abduction** searches for missing premises:
- Enumerates 1-2 atom hypotheses from lexicon
- Tests each with E-prover (does H enable proof? is H consistent?)
- Minimizes to smallest working set

91.9% of repairs are FOL (not AF). Philosophy is more about missing **content** than dialectical **structure**.

But repairs can be "trivial": adding the goal as a premise. This is formally valid but semantically circular. I debated filtering these out, but they're informative: they reveal when text asserts rather than proves.

From 99 repairs, 87.9% verified successfully. Non-trivial repairs find genuine missing intermediate steps (e.g., bridge predicates enabling modus ponens).

## Graph Metrics: What 95 Arguments Look Like

The corpus reveals patterns:

**Structure:**
- Average: 4.7 nodes, 3.3 edges
- Range: 1-11 nodes
- Density: 0.208 (sparse, not densely connected)
- Components: 1.51 avg (often disconnected fragments)

**Edge distribution:**
- 96.5% support edges
- 3.5% attack edges
- Philosophical arguments are **not primarily dialectical**
- They're linear chains of support, not adversarial debates

**Issues vs. complexity:**
- Queries WITH issues: avg 4.6 nodes
- Queries WITHOUT issues: avg 4.8 nodes
- Graph complexity doesn't predict logical issues

This surprised me. I expected complexity → issues. Instead, issues come from **semantic gaps** (predicate mismatch, missing content), not structural complexity.

## Reflections: Structure vs. Insight

I started with the hypothesis: LLM + logic = better argument analysis.

What I found:
- **The LLM** extracts structure but can't guarantee semantic correctness
- **The logic** verifies formal validity but misses what makes arguments interesting
- **The graph** makes implicit structure explicit, even when verification fails

An unstructured LLM might provide richer insights:
- Contextual interpretation (historical, cultural)
- Explaining *why* premises are plausible
- Identifying implicit world knowledge
- Nuanced critique beyond "unsupported inference"

But the structured approach provides:
- **Precision**: Explicit nodes, edges, predicates
- **Verification**: FOL proofs (when possible), AF acceptance
- **Reproducibility**: Same text → same graph
- **Systematic detection**: 110 issues found across corpus

The tradeoff: **precision vs. richness**.

### What I'd Do Differently

**Less formalization?**
Maybe the graph doesn't need to be FOL-compilable. Keep it as a visual/conceptual tool, don't force everything into predicate logic.

**Better extraction?**
- More sophisticated predicate canonicalization
- Entity extraction and coreference
- Multi-stage LLM repair (not just one-shot)

**Different formal target?**
- Defeasible logic instead of classical FOL
- Probabilistic argumentation
- Just AF, no FOL at all

**More conservative repairs?**
- Filter trivial repairs (goal = premise)
- Require human approval before applying
- Rank by semantic plausibility, not just cost

### The Disappointment

I wanted the logic to capture the essence of arguments. It doesn't. Formalizing *reduces* rather than *enhances* understanding for most philosophical texts.

The 32.6% that prove are simple conditionals or trivial axiom = conjecture. The interesting 67.4%—Nietzsche on slave morality, Heidegger on language, Aristotle on virtue—resist formalization. The subtlety lives in the semantics, not the syntax.

### The Value

But the graph **does** have value:

It makes **hidden structure visible**:
- Schweitzer asserts, doesn't prove
- Aristotle refines conditionally without establishing base claims
- Schopenhauer's dialectical tension (suffering vs. escape)

It enables **systematic analysis**:
- 110 issues detected across 95 queries
- Patterns: philosophical arguments are support-heavy, not dialectical
- Repairs reveal common gaps (missing premises, not attacks)

It provides a **map**, not a verification:
- Like a blueprint vs. a building inspection
- Shows architecture, doesn't prove soundness
- Useful for understanding, not replacing judgment

## Conclusion: The Map is the Artifact

The Argument Debugger set out to verify arguments with logic. It ended up producing maps that reveal structure—sometimes clarifying, sometimes reducing, always making explicit what was implicit.

The graph representation has independent value, even when formal verification fails. It's a tool for understanding argument structure, not replacing argument quality.

Perhaps that's enough: a way to see the bones of an argument, to trace the flow from premise to conclusion, to spot the gaps and circles and unsupported leaps. The logic can't capture the subtlety, but the map can show where the subtlety lives.

The subtlety remains in the semantics—in what "pleasure" means to Epicurus, in what "Being" means to Heidegger, in what "reverence for life" means to Schweitzer. The structure can be extracted, canonicalized, verified. But the meaning? That still requires reading, interpreting, thinking.

The Argument Debugger makes the structure visible. The rest is still philosophy.

---

- **Dataset:** 95 arguments collected at [argir.metareflective.app](https://argir.metareflective.app)
- **Code:** Available at [github.com/namin/argir](https://github.com/namin/argir)
- **Technical documentation:** See `/docs` for deep dives on FOL translation, repair strategies, and system architecture
