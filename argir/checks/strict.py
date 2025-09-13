from __future__ import annotations
from typing import List, Dict, Any, Set
from ..core.model import ARGIR, Statement, NodeRef

Fatal = Dict[str, Any]

def _has_atoms(stmt: Statement|None) -> bool:
    return bool(stmt and stmt.atoms)

def validate_edge_sources_have_content(u: ARGIR) -> List[Fatal]:
    """Any node used in an edge must have a conclusion (with atoms) or a rule."""
    used: Set[str] = {e.source for e in u.graph.edges} | {e.target for e in u.graph.edges}
    bad = []
    for n in u.graph.nodes:
        if n.id in used and not n.rule and not _has_atoms(n.conclusion):
            bad.append({
                "kind": "edge_source_empty",
                "node": n.id,
                "message": "Node participates in an edge but has neither conclusion atoms nor a rule."
            })
    return bad

def validate_rule_completeness(u: ARGIR) -> List[Fatal]:
    """Every rule must have ≥1 antecedent atom AND ≥1 consequent atom."""
    bad = []
    for n in u.graph.nodes:
        if n.rule:
            ants = sum(len(s.atoms) for s in (n.rule.antecedents or []))
            cons = sum(len(s.atoms) for s in (n.rule.consequents or []))
            if ants == 0 or cons == 0:
                bad.append({
                    "kind": "rule_incomplete",
                    "node": n.id,
                    "message": "Rule must have ≥1 antecedent atom and ≥1 consequent atom."
                })
    return bad

def validate_inference_has_bridge(u: ARGIR) -> List[Fatal]:
    """Derived conclusions must be licensed by a rule on the node OR a Ref to some rule node."""
    rule_ids = {n.id for n in u.graph.nodes if n.rule}
    bad = []
    for n in u.graph.nodes:
        if n.premises and _has_atoms(n.conclusion):
            has_rule_here = bool(n.rule)
            has_ref_to_rule = any(isinstance(p, NodeRef) and p.ref in rule_ids for p in n.premises)
            if not (has_rule_here or has_ref_to_rule):
                bad.append({
                    "kind": "inference_missing_rule",
                    "node": n.id,
                    "message": "Derived conclusion lacks a rule or a Ref to a rule node."
                })
    return bad

def strict_validate(u: ARGIR) -> List[Fatal]:
    fatals: List[Fatal] = []
    fatals += validate_edge_sources_have_content(u)
    fatals += validate_rule_completeness(u)
    fatals += validate_inference_has_bridge(u)
    return fatals