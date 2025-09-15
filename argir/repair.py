# argir/repair.py
from __future__ import annotations
import json
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass

# Type for LLM call function
LLMCall = Callable[[str], str]  # prompt -> JSON response string

def _iter_statements(soft_ir: dict):
    """Yield (node, location, statement) for every statement in the soft IR."""
    for n in soft_ir.get("graph", {}).get("nodes", []):
        # Check premises
        for i, p in enumerate(n.get("premises", [])):
            if isinstance(p, dict) and p.get("pred"):
                yield (n, ("premises", i), p)

        # Check conclusion
        if n.get("conclusion") and isinstance(n["conclusion"], dict):
            yield (n, ("conclusion", None), n["conclusion"])

        # Check rule components
        if n.get("rule"):
            rule = n["rule"]
            for i, s in enumerate(rule.get("antecedents", [])):
                if isinstance(s, dict) and s.get("pred"):
                    yield (n, ("rule.antecedents", i), s)
            for i, s in enumerate(rule.get("consequents", [])):
                if isinstance(s, dict) and s.get("pred"):
                    yield (n, ("rule.consequents", i), s)
            for i, s in enumerate(rule.get("exceptions", [])):
                if isinstance(s, dict) and s.get("pred"):
                    yield (n, ("rule.exceptions", i), s)


def collect_surface_predicates(soft_ir: dict) -> List[str]:
    """Collect all unique surface predicate strings from the soft IR."""
    preds = set()
    for _, _, stmt in _iter_statements(soft_ir):
        if stmt.get("pred"):
            preds.add(stmt["pred"])
    return sorted(preds)


def unify_predicates_via_llm(soft_ir: dict, llm_call: LLMCall) -> Dict[str, str]:
    """
    Ask the LLM to unify surface predicates to canonical forms.
    Applies the mapping in-place to the soft IR.
    Returns the mapping for logging.
    """
    from .prompts import repair_prompt_for_predicate_unification

    surface_preds = collect_surface_predicates(soft_ir)
    if not surface_preds:
        return {}

    # Get unification mapping from LLM
    prompt = repair_prompt_for_predicate_unification(surface_preds)
    response = llm_call(prompt)

    try:
        mapping = json.loads(response)
        if not isinstance(mapping, dict):
            raise ValueError("Expected dict mapping")
    except Exception as e:
        print(f"Warning: LLM predicate unification failed: {e}")
        return {}

    # Apply mapping to all statements
    for node, location, stmt in _iter_statements(soft_ir):
        if stmt.get("pred") and stmt["pred"] in mapping:
            stmt["pred"] = mapping[stmt["pred"]]

    return mapping


def _compact_rule(node: dict) -> dict:
    """Create a compact representation of a rule for the LLM prompt."""
    if not node.get("rule"):
        return {}

    rule = node["rule"]

    def stmt_to_compact(s):
        if not isinstance(s, dict):
            return {}
        return {
            "pred": s.get("pred", ""),
            "args": s.get("args", []),
            "polarity": s.get("polarity", "pos")
        }

    return {
        "rule_id": node.get("id", ""),
        "name": rule.get("name", ""),
        "antecedents": [stmt_to_compact(s) for s in rule.get("antecedents", [])],
        "consequents": [stmt_to_compact(s) for s in rule.get("consequents", [])]
    }


def fill_exceptions_via_llm(soft_ir: dict, source_text: str, llm_call: LLMCall) -> None:
    """
    For rules missing exceptions, ask the LLM to extract them from source text.
    Modifies soft_ir in place.
    """
    from .prompts import repair_prompt_for_rule_exceptions

    # Find rules that might need exceptions
    rules_to_check = []
    for node in soft_ir.get("graph", {}).get("nodes", []):
        if node.get("rule"):
            rule = node["rule"]
            # Check rules that don't already have exceptions
            if not rule.get("exceptions"):
                rules_to_check.append(node)

    if not rules_to_check:
        return

    # Ask LLM about exceptions
    compact_rules = [_compact_rule(n) for n in rules_to_check]
    prompt = repair_prompt_for_rule_exceptions(source_text, compact_rules)
    response = llm_call(prompt)

    try:
        exception_data = json.loads(response)
        if not isinstance(exception_data, list):
            exception_data = []
    except Exception as e:
        print(f"Warning: LLM exception extraction failed: {e}")
        return

    # Apply exceptions to rules
    exceptions_by_id = {item["rule_id"]: item["exceptions"]
                        for item in exception_data
                        if isinstance(item, dict) and item.get("rule_id")}

    for node in rules_to_check:
        node_id = node.get("id", "")
        if node_id in exceptions_by_id:
            exceptions = exceptions_by_id[node_id]
            if exceptions and isinstance(exceptions, list):
                if not node["rule"].get("exceptions"):
                    node["rule"]["exceptions"] = []
                node["rule"]["exceptions"].extend(exceptions)


def unify_polarity_via_llm(soft_ir: dict, llm_call: LLMCall) -> Dict[str, dict]:
    """
    Ask the LLM to identify antonym/negation relations and map them to
    canonical predicates with polarity.
    Returns the polarity mapping for logging.
    """
    from .prompts import repair_prompt_for_predicate_polarity

    surface_preds = collect_surface_predicates(soft_ir)
    if not surface_preds:
        return {}

    # Get polarity mapping from LLM
    prompt = repair_prompt_for_predicate_polarity(surface_preds)
    response = llm_call(prompt)

    try:
        polarity_map = json.loads(response)
        if not isinstance(polarity_map, dict):
            raise ValueError("Expected dict mapping")
    except Exception as e:
        print(f"Warning: LLM polarity unification failed: {e}")
        return {}

    # Apply mapping to all statements
    for node, location, stmt in _iter_statements(soft_ir):
        pred = stmt.get("pred")
        if pred and pred in polarity_map:
            mapping = polarity_map[pred]
            if isinstance(mapping, dict):
                # Update predicate to canonical form
                if "canonical" in mapping:
                    stmt["pred"] = mapping["canonical"]
                # Update polarity
                if "polarity" in mapping:
                    current_polarity = stmt.get("polarity", "pos")
                    new_polarity = mapping["polarity"]
                    # If statement was already negative and we're applying negative mapping,
                    # the result is positive (double negation)
                    if current_polarity == "neg" and new_polarity == "neg":
                        stmt["polarity"] = "pos"
                    elif current_polarity == "pos" and new_polarity == "neg":
                        stmt["polarity"] = "neg"
                    # else keep as is (pos+pos=pos, neg+pos=neg)

    return polarity_map


def apply_llm_repairs(soft_ir: dict, source_text: str, llm_call: LLMCall) -> dict:
    """
    Apply all LLM-based repairs to the soft IR.
    Returns info about what was repaired.
    """
    info = {}

    # 1. Unify predicates
    pred_mapping = unify_predicates_via_llm(soft_ir, llm_call)
    if pred_mapping:
        info["predicate_unification"] = pred_mapping

    # 2. Unify polarity (antonyms/negations)
    polarity_mapping = unify_polarity_via_llm(soft_ir, llm_call)
    if polarity_mapping:
        info["polarity_unification"] = polarity_mapping

    # 3. Fill missing exceptions
    # Only do this if we don't already have exceptions from the initial extraction
    fill_exceptions_via_llm(soft_ir, source_text, llm_call)

    return info