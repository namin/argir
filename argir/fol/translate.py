from __future__ import annotations
from typing import List, Tuple, Optional
from .ast import *
from ..core.model import ARGIR, Statement, NodeRef, InferenceStep

def _to_term(t): return Const(t.name) if t.kind=="Const" else Var(t.name)
def _to_atom(a): return Atom(Pred(a.pred, len(a.args)), [_to_term(x) for x in a.args], a.negated)

def stmt_to_formula(s: Statement) -> Formula:
    if s.atoms:
        phi: Formula = _to_atom(s.atoms[0])
        for a in s.atoms[1:]: phi = And(phi, _to_atom(a))
        return phi
    return Atom(Pred("nl_"+(s.text[:20].strip().replace(" ","_") or "stmt"), 0), [])

def _conj(forms: list[Formula]) -> Formula:
    assert len(forms) >= 1
    phi = forms[0]
    for f in forms[1:]:
        phi = And(phi, f)
    return phi

def rule_to_formula(n: InferenceStep, *, fol_mode: str = "classical") -> Formula:
    if not n.rule:
        return Atom(Pred("nl_rule_"+n.id, 0), [])
    ants = [stmt_to_formula(s) for s in (n.rule.antecedents or [])]
    cons = [stmt_to_formula(s) for s in (n.rule.consequents or [])]
    if fol_mode == "defeasible" and n.rule.exceptions:
        exc = None
        for s in n.rule.exceptions:
            psi = stmt_to_formula(s)
            exc = psi if exc is None else And(exc, psi)
        if ants and cons:
            ante = _conj(ants + ([Not(exc)] if exc else []))
            return Implies(ante, _conj(cons) if len(cons)>1 else cons[0])
    if ants and cons:
        return Implies(_conj(ants), _conj(cons) if len(cons)>1 else cons[0])
    if cons:
        return _conj(cons) if len(cons)>1 else cons[0]
    if ants:
        return _conj(ants) if len(ants)>1 else ants[0]
    return Atom(Pred("nl_rule_"+n.id, 0), [])

def premise_to_statement(p, id2node) -> Statement:
    if isinstance(p, NodeRef):
        tgt = id2node.get(p.ref)
        if tgt and tgt.conclusion:
            return tgt.conclusion
        if tgt and tgt.rule:
            return Statement(text=f"<rule:{tgt.id}>")
        if tgt and tgt.premises and len(tgt.premises)==1 and not tgt.rule and not tgt.conclusion:
            prem = tgt.premises[0]
            if isinstance(prem, Statement): return prem
        return Statement(text=f"<ref:{p.ref}>")
    return p

def choose_goal_node(u: ARGIR, goal_id: Optional[str] = None) -> Optional[str]:
    """Choose goal node with improved heuristics:
    1. Use explicit goal_id if provided
    2. Find nodes that are not referenced as premises (inference sinks)
    3. Prefer nodes that are attack sinks (no outgoing attacks)
    4. Prefer nodes with more complex derivations (have premises)
    """
    if goal_id:
        return goal_id

    # Find nodes referenced as premises
    ref_targets = set()
    for n in u.graph.nodes:
        for p in n.premises:
            if isinstance(p, NodeRef):
                ref_targets.add(p.ref)

    # Find nodes that are sources of attacks
    attack_sources = set()
    attack_targets = set()
    for e in u.graph.edges:
        if e.kind == "attack":
            attack_sources.add(e.source)
            attack_targets.add(e.target)

    # Primary candidates: conclusions not referenced as premises
    primary = [n for n in u.graph.nodes
              if n.conclusion and n.premises
              and n.id not in ref_targets]

    # If only one, that's our goal
    if len(primary) == 1:
        return primary[0].id

    # If multiple, prefer:
    # 1. Nodes with negated conclusions (often "should NOT" statements)
    # 2. Nodes that are not attack sources (defensive positions)
    # 3. Nodes with more complex derivations (more premises)
    if primary:
        # Check for negated conclusions (final "should NOT" statements)
        negated = [n for n in primary
                  if n.conclusion.atoms and n.conclusion.atoms[0].negated]
        if len(negated) == 1:
            return negated[0].id

        # Prefer non-attackers
        non_attackers = [n for n in primary if n.id not in attack_sources]
        if len(non_attackers) == 1:
            return non_attackers[0].id

        # Pick the one with most premises (most complex)
        candidates = negated if negated else (non_attackers if non_attackers else primary)
        return max(candidates, key=lambda n: len(n.premises)).id

    # Secondary: any conclusion not referenced as premise
    secondary = [n for n in u.graph.nodes
                if n.conclusion
                and n.id not in ref_targets]
    if secondary:
        # Apply same preference for negated conclusions
        negated = [n for n in secondary
                  if n.conclusion.atoms and n.conclusion.atoms[0].negated]
        if len(negated) == 1:
            return negated[0].id

        # Pick most complex
        return max(secondary, key=lambda n: len(n.premises) if n.premises else 0).id

    return None

def argir_to_fof(u: ARGIR, *, fol_mode: str = "classical", goal_id: Optional[str] = None) -> List[Tuple[str,str]]:
    from .tptp import fof
    out: List[Tuple[str,str]] = []
    id2node = {n.id: n for n in u.graph.nodes}
    for n in u.graph.nodes:
        if n.rule:
            out.append((f"rule_{n.id}", fof(f"rule_{n.id}", "axiom", rule_to_formula(n, fol_mode=fol_mode))))
    for n in u.graph.nodes:
        if not n.rule and not n.conclusion and n.premises:
            for i, p in enumerate(n.premises):
                if isinstance(p, Statement):
                    out.append((f"prem_{n.id}_{i}", fof(f"prem_{n.id}_{i}", "axiom", stmt_to_formula(p))))
    for n in u.graph.nodes:
        if not n.rule and not n.premises and n.conclusion:
            out.append((f"fact_{n.id}", fof(f"fact_{n.id}", "axiom", stmt_to_formula(n.conclusion))))
    for n in u.graph.nodes:
        if n.conclusion and n.premises:
            prem_stmts = [premise_to_statement(p, id2node) for p in n.premises]
            prem_forms: list[Formula] = []
            for s in prem_stmts:
                if isinstance(s, Statement) and s.text.startswith("<rule:"):
                    ref_id = s.text[len("<rule:"):-1]
                    tgt = id2node.get(ref_id)
                    prem_forms.append(rule_to_formula(tgt, fol_mode=fol_mode) if tgt else Atom(Pred("nl_missing_rule_"+ref_id, 0), []))
                else:
                    prem_forms.append(stmt_to_formula(s))
            prem = _conj(prem_forms) if len(prem_forms)>1 else prem_forms[0]
            out.append((f"node_{n.id}_link", fof(f"node_{n.id}_link", "axiom", Implies(prem, stmt_to_formula(n.conclusion)))))
    chosen = choose_goal_node(u, goal_id=goal_id)
    if chosen:
        g = id2node.get(chosen)
        if g and g.conclusion:
            out.append(("goal", fof("goal", "conjecture", stmt_to_formula(g.conclusion))))
    return out
