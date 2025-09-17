# argir/prompts.py

SOFT_EXTRACTION_SYS = """You convert natural-language arguments into a SOFT IR JSON format.
You MUST output ONLY the SOFT schema below. DO NOT use the strict ARGIR schema (no "atoms", no "text" fields in statements).

Output a single JSON object with this structure:
{
  "version": "soft-0.1",
  "source_text": "<the original text>",
  "graph": {
    "nodes": [
      {
        "id": "<optional: n1, r1, etc>",
        "span": "<IMPORTANT: the exact sentence(s) from the source text that this node represents>",
        "premises": [
          // Either a Statement or a Ref to another node
          {"pred": "...", "args": [{"value": "..."}], "polarity": "pos"/"neg"}
          // OR
          {"kind": "Ref", "ref": "<node_id>"}
        ],
        "rule": {  // Optional: for nodes representing rules
          "name": "<optional name>",
          "strict": true/false,
          "antecedents": [<Statements>],
          "consequents": [<Statements>],
          "exceptions": [<Statements>]
        },
        "conclusion": <Statement>,  // Optional; REQUIRED if this node is the goal with kind="conclusion"
        "rationale": "<optional explanation>"
      }
    ],
    "edges": [
      {
        "source": "<node_id>",
        "target": "<node_id>",
        "kind": "support" or "attack",
        "attack_kind": "<optional: undercut, rebut>",
        "rationale": "<optional>"
      }
    ]
  },
  "goal": {                      // REQUIRED: choose exactly one main claim
    "kind": "conclusion" | "rule",
    "node_id": "<id>"
  },
  "metadata": {
    "goal_id": "<same as goal.node_id>"   // convenience mirror
  }
}

Statement format:
{
  "pred": "<predicate name>",           // Use natural language as it appears in the text
  "args": [{"value": "<arg>"}],         // Simple strings; use X,Y,Z for variables, proper names for constants
  "polarity": "pos" | "neg",            // Default "pos"
  "quantifiers": [                      // OPTIONAL; REQUIRED for general (quantified) GOAL conclusions
    {"kind": "forall" | "exists", "vars": ["X","Y"]}
  ]
}

Guidelines:
- Use NATURAL LANGUAGE predicates as they appear in the text
- DO NOT pre-canonicalize predicates with underscores
- Keep predicates readable and close to the original phrasing
- Node IDs are optional (we'll assign stable ones)
- For simple conditionals, create a rule node with antecedents/consequents
- For arguments with premises leading to conclusions, create inference nodes
- Use "attack" edges for counterarguments, exceptions, or rebuttals
- Use "support" edges for positive relationships between arguments
- We'll automatically canonicalize predicates later - focus on clarity

CRITICAL for defeasible reasoning and exceptions:
- Words like "Normally", "Usually", "Typically", "Generally" indicate defeasible rules (set strict=false)
- When a general rule is followed by a specific counterexample that contradicts it:
  * Add the counterexample conditions to the rule's "exceptions" field
  * Example: "Birds can fly. Ostriches are birds. Ostriches cannot fly."
    → Create rule: bird(X) => can_fly(X) with exceptions: [bird(ostriches), ~can_fly(ostriches)]
  * Example: "If it rains, streets get wet. However, covered streets stay dry even when raining."
    → Create rule: rains => streets_wet with exceptions: [covered_streets]
- Also create attack edges from exception instances to show they undermine the general rule

CRITICAL for generalizations and rules:
- ALWAYS use variables (X, Y, Z; optional digits) for general statements.
- "All/Every S are P" → make a RULE with antecedent: {"pred":"S", "args":[{"value":"X"}]}, consequent: {"pred":"P", "args":[{"value":"X"}]}.
- "Some/There exists S that are P" → prefer a conclusion with variables and quantifiers=[{"kind":"exists","vars":["X"]}].
- "Not all S are P" → prefer a counterexample conclusion with two predicates: S(X) and ~P(X) with quantifiers=[{"kind":"exists","vars":["X"]}].
- NEVER create fused/macro predicates that combine a subject/class with a property.
  Examples of FORBIDDEN fused predicates (any arity): "bird_can_fly", "birds_are_mortal",
  "all_birds_can_fly", "not_all_birds_can_fly".
  Instead:
    • Represent the subject/class as its own predicate: bird(X)
    • Represent the property as its own predicate: fly(X) or can_fly(X)
    • For generalizations ("all", "most", "normally", "typically"), create a RULE node:
        antecedents: [{pred:"bird", args:[{"value":"X"}]}]
        consequents: [{pred:"fly", args:[{"value":"X"}]}]
  This applies to ALL such cases, not only 0-arity slogans.
- Variables start with uppercase letters (X, Y, Z, X1, Y2, ...).

GOAL requirements:
- You MUST choose exactly one GOAL. Set both goal.node_id and metadata.goal_id to that node's id.
- If the GOAL is a GENERAL claim (cues: 'all', 'every', 'any', 'no/none', 'not all', 'some', 'there exists'):
  the GOAL node's CONCLUSION MUST use variables and include quantifiers[] (forall/exists as appropriate).
- If the GOAL is about an INDIVIDUAL (e.g., 'socrates'), keep it ground (quantifiers[] may be empty).

Example (GOOD):
  "Normally, birds can fly."
  → Create a RULE node:
    antecedents: [{"pred":"bird", "args":[{"value":"X"}]}]
    consequents: [{"pred":"can_fly", "args":[{"value":"X"}]}]

Example (BAD - DO NOT DO THIS):
  "Normally, birds can fly."
  → conclusion: {"pred":"bird_can_fly", "args":[{"value":"X"}]}  # ❌ FORBIDDEN fused predicate

STRICT FORMAT IS FORBIDDEN IN SOFT MODE:
- Do NOT output "atoms", "text", or any nested ARGIR strict structures in statements.
- Use ONLY the simple pred/args format shown above.
"""

SOFT_EXTRACTION_USER_TEMPLATE = """Convert the following text into SOFT IR format ONLY:

{text}

Remember to:
1. Extract the logical structure (premises, conclusions, rules)
2. Identify support and attack relationships
3. Use natural language predicates as they appear in the source text
4. Choose exactly one GOAL (goal.node_id + metadata.goal_id must point to it)
5. If the GOAL is general, use variables in its conclusion and add quantifiers[] (forall/exists as appropriate)
6. NEVER invent 0-arity macro predicates; NEVER use 'atoms' or 'text' keys in statements
7. Output valid JSON matching the SOFT schema (no strict ARGIR fields)"""

def get_soft_extraction_prompt(text: str, goal_hint: str = None) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for soft extraction."""
    user_prompt = SOFT_EXTRACTION_USER_TEMPLATE.format(text=text)

    # Add goal hint if provided
    if goal_hint:
        user_prompt += f"\n\nIMPORTANT: The main claim to analyze/defend is: '{goal_hint}'"
        user_prompt += "\nSelect the node whose conclusion best matches this claim as the goal."

    return SOFT_EXTRACTION_SYS, user_prompt

def repair_prompt_for_missing_lexicon(preds_missing: list[str]) -> str:
    """Generate repair prompt for missing lexicon entries."""
    return f"""Some predicates are not in the lexicon: {', '.join(preds_missing)}.

For each predicate, either:
1. Choose an existing canonical predicate from the lexicon that means the same thing
2. Propose a new canonical key (lowercase, underscores, no articles)

Return a JSON mapping:
{{
  "surface_pred": "canonical_key",
  ...
}}
"""

def repair_prompt_for_dangling_refs(refs_missing: list[str]) -> str:
    """Generate repair prompt for dangling references."""
    return f"""These node references don't exist: {', '.join(refs_missing)}.

Either:
1. Change the reference to an existing node ID
2. Remove the reference
3. Create the missing node

Return the corrected node or edge structure.
"""

def repair_prompt_for_predicate_unification(all_surface_preds: list[str]) -> str:
    """
    Ask the LLM to unify semantically identical surface predicate names
    (morphology/auxiliaries/modality/synonyms) into a single canonical key
    per concept, *without* losing arity or argument order.
    """
    examples = "\n".join(f"- {p}" for p in sorted(set(all_surface_preds)))
    return f"""Unify the following surface predicate names into consistent canonical keys.
Rules:
- Group semantically identical predicates together
- Use the simplest base form as the canonical key (singular, present tense, no auxiliaries)
- Map morphological variants to the same key (e.g., "men", "man", "is a man" -> "man")
- Map auxiliary variants to the same key (e.g., "will get wet", "gets wet", "get wet" -> "get_wet")
- Use lowercase with underscores for multi-word canonical keys
- Keep distinct meanings separate (e.g., "immortal" vs "mortal" are different)

Return JSON object mapping *each* surface predicate string to a canonical key, e.g.:
{{
  "men": "man",
  "is a man": "man",
  "it rains": "rain",
  "raining": "rain",
  "streets will get wet": "streets_get_wet",
  "streets get wet": "streets_get_wet"
}}

Surface predicates:
{examples}
"""

def repair_prompt_for_rule_exceptions(source_text: str, compact_rules: list) -> str:
    """
    Ask the LLM to infer exception conditions from the source text for given rules.
    """
    import json
    rules_str = json.dumps(compact_rules, indent=2)
    return f"""From the SOURCE TEXT, identify exception conditions for each RULE (if any).

Look for:
- Words like "except", "unless", "however", "but", "normally" that indicate exceptions
- Specific counterexamples that contradict general rules
- Conditions that prevent the normal consequence

For each rule with exceptions, return the exception conditions as statements.
Statement format: {{"pred": "<surface predicate>", "args": [{{"value": "X"}}], "polarity": "pos"/"neg"}}

Return a JSON list; each item: {{"rule_id": "<id>", "exceptions": [<Statements>]}}.
Only include rules that actually have exceptions mentioned in the SOURCE TEXT.
Empty list [] if no exceptions found.

SOURCE TEXT:
\"\"\"{source_text.strip()}\"\"\"

RULES:
{rules_str}
"""

def repair_prompt_for_predicate_polarity(all_surface_preds: list[str]) -> str:
    """
    Ask the LLM to identify antonym/negation relations and map them to
    a canonical predicate with polarity.
    """
    preds_list = "\n".join(f"- {p}" for p in sorted(set(all_surface_preds)))
    return f"""Identify antonym/negation relations among these predicate names and
map them to a canonical predicate with a polarity flag.

Look for:
- Negating prefixes (un-, in-, non-, im-, dis-, a-)
- Lexical antonyms (mortal/immortal, can_fly/cannot_fly, wet/dry)
- Negated forms (is_not_X should map to X with neg polarity)

Return JSON mapping each predicate to its canonical form and polarity:
{{
  "mortal":     {{"canonical": "mortal", "polarity": "pos"}},
  "immortal":   {{"canonical": "mortal", "polarity": "neg"}},
  "can_fly":    {{"canonical": "can_fly", "polarity": "pos"}},
  "cannot_fly": {{"canonical": "can_fly", "polarity": "neg"}}
}}

Rules:
- Use the positive form as canonical when possible
- Only map pairs you are confident are antonyms/negations
- Leave unrelated predicates unmapped (they'll keep their original form)
- If a predicate has no antonym in the list, don't include it

Predicates:
{preds_list}
"""