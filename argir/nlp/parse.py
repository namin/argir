from __future__ import annotations
import json
from typing import Tuple, Dict, Any
from .llm import generate_json

PARSE_SYSTEM = """You MUST output exactly one valid JSON object (no code fences, no prose).
Keys: version, source_text, graph{nodes,edges}, metadata.
Node = {id, premises[], rule?, conclusion?, span?, rationale?}
  Premise = Statement | "nodeId"
  Statement = {text, atoms[], quantifiers[], span?, rationale?, confidence?}
  Rule = {name, strict, antecedents[], consequents[], exceptions[], span?, scheme?, rationale?}
Edge = {source, target, kind: support|attack, attack_kind: rebut|undermine|undercut|unknown|null, rationale?}
Reflect the text faithfully; do NOT invent content.

### Canonical atoms (REQUIRED)
- In `metadata.atom_lexicon`, provide an object whose KEYS are the canonical predicate names you will use (ASCII, snake_case), and whose VALUES are arrays of surface forms you normalized (e.g., {"raining":["it rains","is raining"],"streets_get_wet":["the streets get wet","the streets will get wet"]}).
- Every `atoms[].pred` you emit MUST be one of the KEYS of `metadata.atom_lexicon`. Reuse the same canonical name for the same meaning across rules, facts, and conclusions.
- If unsure, leave `atoms` empty for that statement.
"""

def build_prompt(text: str) -> str:
    return f"""SOURCE TEXT:\n{text}\n\nReturn ONLY the JSON object described above."""

def llm_draft(text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    raw = generate_json(build_prompt(text), system=PARSE_SYSTEM, temperature=0.0)
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError("LLM returned JSON but not an object.")
    return doc, {"raw": doc}
