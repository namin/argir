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

    # Structural warnings (components, sinks, reachability)
    issues += structural_warnings(u)
    return issues

def _connected_components(u: ARGIR) -> list[set[str]]:
    nbr = {n.id: set() for n in u.graph.nodes}
    for e in u.graph.edges:
        a, b = e.source, e.target
        if a in nbr and b in nbr:
            nbr[a].add(b); nbr[b].add(a)
    comps, seen = [], set()
    for nid in nbr:
        if nid in seen: continue
        stack, comp = [nid], set()
        while stack:
            x = stack.pop()
            if x in comp: continue
            comp.add(x); seen.add(x)
            stack.extend(nbr[x])
        comps.append(comp)
    return comps

def structural_warnings(u: ARGIR) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    comps = _connected_components(u)
    if len(comps) > 1:
        issues.append({"kind":"disconnected_components","node":"—",
                       "message": f"Graph has {len(comps)} connected components"})
    # goal component
    goal_id = (u.metadata or {}).get("goal_id") or (u.metadata or {}).get("goal_candidate_id")
    gc = None
    for c in comps:
        if goal_id in c:
            gc = c; break
    if gc is None and comps:
        gc = comps[0]
    # support out-degree
    outdeg = {n.id: 0 for n in u.graph.nodes}
    indeg = {n.id: 0 for n in u.graph.nodes}
    for e in u.graph.edges:
        if e.kind == "support":
            outdeg[e.source] = outdeg.get(e.source, 0) + 1
            indeg[e.target] = indeg.get(e.target, 0) + 1
    if gc:
        sinks = [nid for nid in gc if outdeg.get(nid, 0) == 0]
        if len(sinks) > 1:
            issues.append({"kind":"multiple_conclusions","node":"—",
                           "message": f"Multiple sink conclusions ({len(sinks)}) in the goal component"})
        # reachability
        roots = [nid for nid in gc if indeg.get(nid, 0) == 0]
        seen = set(roots)
        stack = roots[:]
        outs = {}
        for e in u.graph.edges:
            if e.kind == "support":
                outs.setdefault(e.source, set()).add(e.target)
        while stack:
            x = stack.pop()
            for y in outs.get(x, ()):
                if y not in seen:
                    seen.add(y); stack.append(y)
        if goal_id and goal_id not in seen:
            issues.append({"kind":"goal_unreachable","node":str(goal_id),
                           "message":"Goal is not reachable from any support root"})
    return issues