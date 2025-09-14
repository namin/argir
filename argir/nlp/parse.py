from __future__ import annotations
import json
from typing import Tuple, Dict, Any, Callable
from .llm import generate_json, init_llm_client, generate_content, LLM_MODEL
from google.genai import types

PARSE_SYSTEM = """You are an argument parser. Output ONE JSON object that conforms to ARGIR's contract.
If you cannot satisfy ALL constraints below, do NOT guess—re-think and fix before emitting JSON.
Final output MUST be valid JSON only (no prose).

Schema:
Node = {id, premises[], rule?, conclusion?, span?, rationale?}
  Premise = Statement | {"kind":"Ref","ref":"nodeId"}
  Statement = {text?, atoms[], quantifiers[], span?, rationale?, confidence?}
  Rule = {name?, strict?, antecedents[], consequents[], exceptions[], span?, scheme?, rationale?}
    - antecedents/consequents/exceptions are arrays of Statement objects with atoms[]
Edge = {source, target, kind:"support"|"attack", attack_kind?:"rebut"|"undermine"|"undercut"|"unknown"}

Required top-level keys: version, source_text, graph, metadata.
- version: "0.3.x"
- source_text: exactly the user input (verbatim).
- graph: { nodes: InferenceStep[], edges: Edge[] }
- metadata.atom_lexicon: { <canonical_pred>: [example_surface_forms...] , ... }

HARD CONSTRAINTS (must hold in the final JSON):
1) Canonical atoms
   1.1 Every Statement or Rule atom uses atoms[].pred that is a KEY in metadata.atom_lexicon.
   1.2 Do not invent predicates you don't also register in atom_lexicon.

2) Node completeness
   2.1 If a node appears in ANY edge (as source or target), that node MUST have either:
       (a) a non-empty conclusion (Statement with atoms length ≥1), OR
       (b) a rule object with ≥1 atom in antecedents AND ≥1 atom in consequents.
   2.2 If you cannot populate a node used in an edge, remove the edge OR remove the node entirely.

3) Rules for ALL derived conclusions
   3.1 Any node with BOTH premises AND a conclusion MUST either:
       (a) Have its own rule on the node, OR
       (b) Reference a rule node that licenses the inference
   3.2 Create explicit rule nodes for all inferences, including intermediate steps.
   3.3 The main conclusion must be licensed by a rule (strict or defeasible).

4) Edges
   4.1 kind ∈ {"support","attack"}.
   4.2 attack_kind present IFF kind="attack", and attack_kind ∈ {"rebut","undermine","undercut","unknown"}.
   4.3 Edge endpoints must be existing node ids (no dangling references).

5) Text–atom alignment
   5.1 Every conclusion with atoms must be paraphrasable from source_text.
   5.2 If you add an "implicit claim" node (IC…), it MUST also carry atoms and be connected by an edge.

6) Variables for universal statements
   6.1 For universal rules, use variables (X, Y, Z, W, U, V with optional digits):
       - "All S are P" → rule with antecedent: S(X), consequent: P(X)
       - Variables are {"kind":"Var","name":"X"} in args
   6.2 Avoid 0-arity predicates for generalizations
   6.3 Variables: uppercase single letters with optional digits (X, Y, Z, X1, Y2, etc.)

7) Optional but recommended
   7.1 metadata.conflicts: list of contradictory predicate pairs (e.g., ["should_close","should_not_close_due_to_fear"]).
   7.2 Suggest a single goal candidate id if there is a unique derived conclusion.

SELF-CHECK before emitting JSON (redo/fix if any fail):
- All ids in edges exist in nodes.
- For every edge source: node has conclusion OR rule (2.1).
- For every rule: antecedents[] and consequents[] arrays, each with ≥1 Statement having atoms.
- Every atoms[].pred ∈ keys(metadata.atom_lexicon).
- Every node with premises AND conclusion has a rule or references a rule node (3.1).
- There is at least one rule that licenses the main conclusion (3.3).

Output: ONLY the final JSON object. No explanations."""

def build_prompt(text: str) -> str:
    return f"""SOURCE TEXT:\n{text}\n\nReturn ONLY the JSON object described above."""

def llm_draft(text: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    raw = generate_json(build_prompt(text), system=PARSE_SYSTEM, temperature=0.0)
    doc = json.loads(raw)
    if not isinstance(doc, dict):
        raise ValueError("LLM returned JSON but not an object.")
    return doc, {"raw": doc}

def get_llm() -> Callable[[str, str], str]:
    """Return a callable LLM function for soft pipeline."""
    def llm_call(system_prompt: str, user_prompt: str) -> str:
        client = init_llm_client(required=True)
        combined = f"{system_prompt}\n\n{user_prompt}"
        cfg = types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json")
        resp = generate_content(client, contents=combined, config=cfg, model=LLM_MODEL)
        text = getattr(resp, "text", None) or getattr(resp, "output_text", None) or ""
        return text
    return llm_call
