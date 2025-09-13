from __future__ import annotations
from typing import Any, Dict, List, Optional
from ..core.model import ARGIR, ArgumentGraph, InferenceStep, Statement, NodeRef, Rule, Edge, TextSpan, Atom, Term, Quantifier

class CanonicalizationResult:
    def __init__(self, argir: ARGIR, warnings: List[str]):
        self.argir = argir
        self.warnings = warnings

def _clip_span(span: dict, text: str) -> TextSpan:
    start = max(0, int(span.get("start", 0)))
    end = min(len(text), int(span.get("end", 0)))
    if end < start: end = start
    stext = span.get("text") or text[start:end]
    return TextSpan(start=start, end=end, text=stext)

def _num(v) -> Optional[float]:
    if isinstance(v, (int,float)): return float(v)
    if isinstance(v, str):
        s=v.strip().lower()
        if not s or s in {"unknown","n/a","na","none","null"}: return None
        if s.endswith("%"):
            try: return float(s[:-1])/100.0
            except: return None
        try: return float(s)
        except: return None
    return None

def _atom(a: Any) -> Optional[Atom]:
    if isinstance(a, dict) and "pred" in a:
        args = []
        for x in a.get("args", []) or []:
            if isinstance(x, dict) and "name" in x:
                kind = "Var" if x.get("kind")=="Var" else "Const"
                args.append(Term(kind=kind, name=str(x["name"])))
            elif isinstance(x, str):
                args.append(Term(kind="Const", name=x))
        return Atom(pred=str(a.get("pred","p")), args=args, negated=bool(a.get("negated", False)))
    if isinstance(a, str) and a.strip():
        return Atom(pred=a.strip(), args=[], negated=False)
    return None

def _quant(q: Any) -> Optional[Quantifier]:
    if isinstance(q, dict) and q.get("var"):
        k=q.get("kind")
        if k in ("forall","exists"):
            return Quantifier(kind=k, var=str(q["var"]), sort=(str(q["sort"]) if q.get("sort") else None))
    return None

def _stmt(s: Any, src: str) -> Statement:
    if not isinstance(s, dict):
        return Statement(text=str(s))
    span = _clip_span(s["span"], src) if isinstance(s.get("span"), dict) else None
    atoms = [a for a in (_atom(x) for x in (s.get("atoms") or [])) if a]
    quants = [q for q in (_quant(x) for x in (s.get("quantifiers") or [])) if q]
    return Statement(text=str(s.get("text","")), atoms=atoms, quantifiers=quants, span=span, rationale=s.get("rationale"), confidence=_num(s.get("confidence")))

def canonicalize(draft: Dict[str, Any]) -> CanonicalizationResult:
    src = str(draft.get("source_text", draft.get("text","")))
    g = draft.get("graph") or {}
    raw_nodes = g.get("nodes") or []
    raw_edges = g.get("edges") or []
    ids = set()
    for i, n in enumerate(raw_nodes):
        nid = str(n.get("id", f"n{i}"))
        if nid in ids: nid = f"{nid}_{i}"
        ids.add(nid)
    nodes: List[InferenceStep] = []
    warns: List[str] = []
    for i, n in enumerate(raw_nodes):
        nid = str(n.get("id", f"n{i}"))
        span = _clip_span(n["span"], src) if isinstance(n.get("span"), dict) else None
        rule=None; rraw=n.get("rule")
        if isinstance(rraw, dict):
            rspan = _clip_span(rraw["span"], src) if isinstance(rraw.get("span"), dict) else None
            rule = Rule(name=str(rraw.get("name","r")),
                strict=bool(rraw.get("strict", False)) if isinstance(rraw.get("strict", False), bool) else False,
                antecedents=[_stmt(s, src) for s in (rraw.get("antecedents") or [])],
                consequents=[_stmt(s, src) for s in (rraw.get("consequents") or [])],
                exceptions=[_stmt(s, src) for s in (rraw.get("exceptions") or [])],
                span=rspan, scheme=rraw.get("scheme"), rationale=rraw.get("rationale"))
        prem = []
        for p in (n.get("premises") or []):
            if isinstance(p, str) and p in ids:
                prem.append(NodeRef(ref=p))
            elif isinstance(p, dict) and p.get("kind") == "Ref" and p.get("ref") in ids:
                prem.append(NodeRef(ref=p.get("ref"), note=p.get("note")))
            else:
                prem.append(_stmt(p, src) if isinstance(p, dict) else Statement(text=str(p)))
        concl = _stmt(n["conclusion"], src) if isinstance(n.get("conclusion"), dict) else None
        nodes.append(InferenceStep(id=nid, premises=prem, rule=rule, conclusion=concl, span=span, rationale=n.get("rationale")))
    edges: List[Edge] = []
    for e in raw_edges:
        kind = e.get("kind","support")
        if kind not in ("support","attack"):
            warns.append("edge kind normalized to support"); kind="support"
        atk = e.get("attack_kind")
        if kind=="attack" and atk not in ("rebut","undermine","undercut","unknown"):
            atk = "unknown"
        if kind=="support": atk = None
        edges.append(Edge(source=str(e.get("source","")), target=str(e.get("target","")), kind=kind, attack_kind=atk, rationale=e.get("rationale")))
    argir = ARGIR(version=str(draft.get("version","0.3.3")), source_text=src, spans_indexed=True, graph=ArgumentGraph(nodes=nodes, edges=edges), metadata=draft.get("metadata",{}))
    # Enforce canonical atom lexicon (alias accepted)
    def _extract_lexicon(meta: dict):
        if not isinstance(meta, dict): return None
        if isinstance(meta.get("atom_lexicon"), dict) and meta["atom_lexicon"]: return meta["atom_lexicon"]
        if isinstance(meta.get("symbols"), dict) and isinstance(meta["symbols"].get("predicates"), dict) and meta["symbols"]["predicates"]:
            return meta["symbols"]["predicates"]
        return None
    lex = _extract_lexicon(draft.get("metadata", {}))
    if not isinstance(lex, dict) or not lex:
        raise ValueError("metadata.atom_lexicon (or symbols.predicates) missing or empty; model must supply canonical atom lexicon.")
    allowed = set(str(k) for k in lex.keys())
    errors: List[str] = []
    for n in argir.graph.nodes:
        for p in n.premises:
            if hasattr(p, "atoms"):
                for a in p.atoms:
                    if a.pred not in allowed: errors.append(f"node {n.id} premise atom '{a.pred}' not in lexicon")
        if n.rule:
            for s in n.rule.antecedents:
                for a in s.atoms:
                    if a.pred not in allowed: errors.append(f"node {n.id} rule antecedent atom '{a.pred}' not in lexicon")
            for s in n.rule.consequents:
                for a in s.atoms:
                    if a.pred not in allowed: errors.append(f"node {n.id} rule consequent atom '{a.pred}' not in lexicon")
            for s in n.rule.exceptions:
                for a in s.atoms:
                    if a.pred not in allowed: errors.append(f"node {n.id} rule exception atom '{a.pred}' not in lexicon")
        if n.conclusion:
            for a in n.conclusion.atoms:
                if a.pred not in allowed: errors.append(f"node {n.id} conclusion atom '{a.pred}' not in lexicon")
    if errors:
        details = "; ".join(errors[:12])
        if len(errors) > 12: details += f" ... (+{len(errors)-12} more)"
        raise ValueError("Atom predicates must be canonical per metadata lexicon: " + details)
    try:
        if isinstance(argir.metadata, dict) and "atom_lexicon" not in argir.metadata:
            argir.metadata["atom_lexicon"] = lex
    except Exception:
        pass
    return CanonicalizationResult(argir, warns)
