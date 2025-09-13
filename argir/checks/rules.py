from __future__ import annotations
from typing import List, Dict, Any
from ..core.model import ARGIR, Statement, NodeRef

Finding = Dict[str, Any]

def _txt(s: Statement|None) -> str:
    return (s.text if s and s.text else "").strip()

def derivability_gap(argir: ARGIR) -> List[Finding]:
    out: List[Finding] = []
    rule_nodes = {n.id for n in argir.graph.nodes if n.rule is not None}
    for n in argir.graph.nodes:
        has_prem = len(n.premises) > 0
        has_concl = bool(n.conclusion and _txt(n.conclusion))
        has_rule = n.rule is not None
        if not has_rule and has_prem:
            for p in n.premises:
                if isinstance(p, NodeRef) and p.ref in rule_nodes:
                    has_rule = True
                    break
        if has_prem and not has_concl:
            out.append({"kind":"derivability_gap","node":n.id,"message":"Premises present but conclusion missing."})
        elif has_prem and has_concl and not has_rule:
            out.append({"kind":"derivability_gap","node":n.id,"message":"Premises and conclusion present but rule missing."})
    return out

def circular_support(argir: ARGIR) -> List[Finding]:
    adj = {}
    for e in argir.graph.edges:
        if e.kind == "support":
            adj.setdefault(e.source, []).append(e.target)
    vis=set(); stack=set(); cycles=[]
    def dfs(v, path):
        vis.add(v); stack.add(v)
        for w in adj.get(v, []):
            if w not in vis: dfs(w, path+[w])
            elif w in stack: cycles.append(path+[w])
        stack.remove(v)
    for n in argir.graph.nodes:
        if n.id not in vis: dfs(n.id, [n.id])
    return [{"kind":"circular_support","cycle":c} for c in cycles]

def attack_support_mismatch(argir: ARGIR) -> List[Finding]:
    out: List[Finding] = []
    for e in argir.graph.edges:
        rat = (e.rationale or "").lower()
        if any(w in rat for w in ["refute","contradict","however"]) and e.kind!="attack":
            out.append({"kind":"edge_mismatch","edge":[e.source,e.target],"message":"Edge rationale suggests attack but typed as support."})
    return out

def run_all(argir: ARGIR) -> List[Finding]:
    f: List[Finding] = []
    f += derivability_gap(argir)
    f += circular_support(argir)
    f += attack_support_mismatch(argir)
    return f
