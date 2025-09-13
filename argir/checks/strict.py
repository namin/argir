from __future__ import annotations
from typing import List, Dict, Any, Set
from ..core.model import ARGIR, Statement, NodeRef

ValidationIssue = Dict[str, Any]

def strict_validate(u: ARGIR) -> List[ValidationIssue]:
    """Validate argument structure and return list of issues."""
    issues: List[ValidationIssue] = []

    # Track which nodes are used in edges and which have rules
    edge_nodes: Set[str] = {e.source for e in u.graph.edges} | {e.target for e in u.graph.edges}
    rule_nodes: Set[str] = {n.id for n in u.graph.nodes if n.rule}

    for node in u.graph.nodes:
        has_atoms = bool(node.conclusion and node.conclusion.atoms)

        # Check: Nodes in edges must have content
        if node.id in edge_nodes and not node.rule and not has_atoms:
            issues.append({
                "kind": "edge_source_empty",
                "node": node.id,
                "message": "Node participates in an edge but has neither conclusion atoms nor a rule."
            })

        # Check: Rules must be complete
        if node.rule:
            ants = sum(len(s.atoms) for s in (node.rule.antecedents or []))
            cons = sum(len(s.atoms) for s in (node.rule.consequents or []))
            if ants == 0 or cons == 0:
                issues.append({
                    "kind": "rule_incomplete",
                    "node": node.id,
                    "message": "Rule must have ≥1 antecedent atom and ≥1 consequent atom."
                })

        # Check: Derived conclusions need rules
        if node.premises and has_atoms:
            has_rule_ref = any(isinstance(p, NodeRef) and p.ref in rule_nodes for p in node.premises)
            if not node.rule and not has_rule_ref:
                issues.append({
                    "kind": "inference_missing_rule",
                    "node": node.id,
                    "message": "Derived conclusion lacks a rule or a Ref to a rule node."
                })

    return issues