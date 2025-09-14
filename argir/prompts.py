# argir/prompts.py

SOFT_EXTRACTION_SYS = """You convert natural language arguments into a Soft IR JSON format.

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
        "conclusion": <Statement>,  // Optional
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
  }
}

Statement format:
{
  "pred": "<predicate name>",  // Keep short & contentful (avoid "is", articles)
  "args": [{"value": "<arg>"}],  // Arguments as simple strings
  "polarity": "pos" or "neg"  // Default "pos"
}

Guidelines:
- Use simple, descriptive predicates (e.g., "raining", "streets_wet", not "it is raining")
- Node IDs are optional (we'll assign stable ones)
- For simple conditionals, create a rule node with antecedents/consequents
- For arguments with premises leading to conclusions, create inference nodes
- Use "attack" edges for counterarguments, exceptions, or rebuttals
- Use "support" edges for positive relationships between arguments
- No need for canonical predicate names - we'll canonicalize them automatically
"""

SOFT_EXTRACTION_USER_TEMPLATE = """Convert the following text into Soft IR format:

{text}

Remember to:
1. Extract the logical structure (premises, conclusions, rules)
2. Identify support and attack relationships
3. Use simple predicate names without articles or "is/are"
4. Output valid JSON matching the schema"""

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