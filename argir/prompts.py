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
- NEVER create 0-arity macro predicates like "all_birds_can_fly" or "not_all_birds_can_fly".
- Variables start with uppercase letters (X, Y, Z, X1, Y2, ...).

GOAL requirements:
- You MUST choose exactly one GOAL. Set both goal.node_id and metadata.goal_id to that node's id.
- If the GOAL is a GENERAL claim (cues: 'all', 'every', 'any', 'no/none', 'not all', 'some', 'there exists'):
  the GOAL node's CONCLUSION MUST use variables and include quantifiers[] (forall/exists as appropriate).
- If the GOAL is about an INDIVIDUAL (e.g., 'socrates'), keep it ground (quantifiers[] may be empty).

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

def get_soft_extraction_prompt(text: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for soft extraction."""
    return SOFT_EXTRACTION_SYS, SOFT_EXTRACTION_USER_TEMPLATE.format(text=text)

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