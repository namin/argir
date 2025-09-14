from __future__ import annotations
from typing import List, Tuple, Optional
from .ast import *
from ..core.model import ARGIR, Statement, NodeRef, InferenceStep

def _to_term(t): return Const(t.name) if t.kind=="Const" else Var(t.name)
def _to_atom(a): return Atom(Pred(a.pred, len(a.args)), [_to_term(x) for x in a.args], a.negated)

def _vars_in_atom(a: Atom) -> set[str]:
    """Collect free variables in an atom."""
    out = set()
    for t in a.args:
        if isinstance(t, Var):
            out.add(t.name)
    return out

def _vars_in_formula(f: Formula) -> set[str]:
    """Collect free variables in a formula."""
    if isinstance(f, Atom):
        return _vars_in_atom(f)
    elif isinstance(f, Not):
        return _vars_in_formula(f.sub)
    elif isinstance(f, And) or isinstance(f, Or) or isinstance(f, Implies) or isinstance(f, Iff):
        return _vars_in_formula(f.left) | _vars_in_formula(f.right)
    elif isinstance(f, Forall) or isinstance(f, Exists):
        # Variables bound by this quantifier
        bound_var = f.var.name if isinstance(f.var, Var) else None
        sub_vars = _vars_in_formula(f.sub)
        if bound_var:
            sub_vars.discard(bound_var)
        return sub_vars
    return set()

def _vars_in_stmt(s: Statement) -> set[str]:
    """Collect free variables in a statement."""
    names = set()
    for a in (s.atoms or []):
        names |= _vars_in_atom(_to_atom(a))
    return names

def _forall_wrap(var_names: set[str], phi: Formula) -> Formula:
    """Wrap a formula with universal quantifiers for all given variables."""
    for v in sorted(var_names):
        phi = Forall(Var(v), phi)
    return phi

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

    # Collect all free variables from antecedents and consequents
    all_vars = set()
    for s in (n.rule.antecedents or []):
        all_vars |= _vars_in_stmt(s)
    for s in (n.rule.consequents or []):
        all_vars |= _vars_in_stmt(s)

    if fol_mode == "defeasible" and n.rule.exceptions:
        exc = None
        for s in n.rule.exceptions:
            psi = stmt_to_formula(s)
            exc = psi if exc is None else And(exc, psi)
            all_vars |= _vars_in_stmt(s)
        if ants and cons:
            ante = _conj(ants + ([Not(exc)] if exc else []))
            core = Implies(ante, _conj(cons) if len(cons)>1 else cons[0])
            return _forall_wrap(all_vars, core)
    if ants and cons:
        core = Implies(_conj(ants), _conj(cons) if len(cons)>1 else cons[0])
        return _forall_wrap(all_vars, core)
    if cons:
        core = _conj(cons) if len(cons)>1 else cons[0]
        return _forall_wrap(all_vars, core)
    if ants:
        core = _conj(ants) if len(ants)>1 else ants[0]
        return _forall_wrap(all_vars, core)
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

def _stmt_has_vars(s: Statement) -> bool:
    """Check if a statement contains variables."""
    return any(t.kind == "Var" for a in (s.atoms or []) for t in a.args)

def _stmt_is_0ary(s: Statement) -> bool:
    """Check if all atoms in a statement are 0-arity."""
    return all(len(a.args) == 0 for a in (s.atoms or []))

def choose_goal_node(u: ARGIR, goal_id: Optional[str] = None) -> Optional[str]:
    """Choose goal node with improved heuristics:
    1. Use explicit goal_id if provided
    2. Prefer conclusions with variables (quantified forms)
    3. De-prioritize 0-arity "macro" predicates
    4. Find nodes that are not referenced as premises (inference sinks)
    5. Prefer nodes with more complex derivations (have premises)
    """
    if goal_id:
        return goal_id

    # Find nodes referenced as premises
    ref_targets = set()
    for n in u.graph.nodes:
        for p in n.premises:
            if isinstance(p, NodeRef):
                ref_targets.add(p.ref)

    # Candidates: inference sinks (not referenced), with conclusions
    candidates = [n for n in u.graph.nodes
                 if n.conclusion and n.id not in ref_targets]

    if not candidates:
        return None

    # 1) Prefer quantified/variable-bearing conclusions
    with_vars = [n for n in candidates if _stmt_has_vars(n.conclusion)]
    if with_vars:
        # Among those with variables, prefer negated ones (common for "not all ...")
        neg = [n for n in with_vars if any(a.negated for a in (n.conclusion.atoms or []))]
        if neg:
            # Pick the most premise-rich among negated variable-bearing
            return max(neg, key=lambda n: len(n.premises) if n.premises else 0).id
        # Otherwise pick the most premise-rich among all variable-bearing
        return max(with_vars, key=lambda n: len(n.premises) if n.premises else 0).id

    # 2) Otherwise, prefer non-0-arity atoms
    non_0ary = [n for n in candidates if not _stmt_is_0ary(n.conclusion)]
    if non_0ary:
        # Among non-0-arity, prefer negated ones
        neg = [n for n in non_0ary if any(a.negated for a in (n.conclusion.atoms or []))]
        if neg:
            return max(neg, key=lambda n: len(n.premises) if n.premises else 0).id
        return max(non_0ary, key=lambda n: len(n.premises) if n.premises else 0).id

    # 3) Fallback: most complex (most premises)
    return max(candidates, key=lambda n: len(n.premises) if n.premises else 0).id

def argir_to_fof(u: ARGIR, *, fol_mode: str = "classical", goal_id: Optional[str] = None) -> List[Tuple[str,str]]:
    from .tptp import fof, formula
    out: List[Tuple[str,str]] = []
    id2node = {n.id: n for n in u.graph.nodes}

    # Collect what conclusions are derived
    concluded_stmts = set()
    for n in u.graph.nodes:
        if n.conclusion:
            # Create a canonical key for the statement
            concluded_stmts.add(formula(stmt_to_formula(n.conclusion)))

    # Export rules
    for n in u.graph.nodes:
        if n.rule:
            out.append((f"rule_{n.id}", fof(f"rule_{n.id}", "axiom", rule_to_formula(n, fol_mode=fol_mode))))

    # Export premise-only nodes (old behavior)
    for n in u.graph.nodes:
        if not n.rule and not n.conclusion and n.premises:
            for i, p in enumerate(n.premises):
                if isinstance(p, Statement):
                    out.append((f"prem_{n.id}_{i}", fof(f"prem_{n.id}_{i}", "axiom", stmt_to_formula(p))))

    # Export fact nodes (conclusions without premises)
    for n in u.graph.nodes:
        if not n.rule and not n.premises and n.conclusion:
            out.append((f"fact_{n.id}", fof(f"fact_{n.id}", "axiom", stmt_to_formula(n.conclusion))))

    # NEW: Export orphan premises as facts
    # These are statement premises that aren't concluded anywhere
    orphan_facts = set()
    orphan_counter = 0
    for n in u.graph.nodes:
        for p in n.premises:
            if isinstance(p, Statement):
                stmt_formula = stmt_to_formula(p)
                stmt_key = formula(stmt_formula)
                if stmt_key not in concluded_stmts and stmt_key not in orphan_facts:
                    orphan_facts.add(stmt_key)
                    orphan_counter += 1
                    out.append((f"orphan_fact_{orphan_counter}",
                              fof(f"orphan_fact_{orphan_counter}", "axiom", stmt_formula)))
    # Export node links (but skip if the node just references a rule)
    for n in u.graph.nodes:
        if n.conclusion and n.premises:
            # Check if this node references a rule
            has_rule_ref = False
            for p in n.premises:
                if isinstance(p, NodeRef):
                    ref_node = id2node.get(p.ref)
                    if ref_node and ref_node.rule:
                        has_rule_ref = True
                        break

            # Skip the link if it references a rule (the rule is already exported)
            if has_rule_ref:
                # Just ensure non-rule premises are captured as orphan facts above
                continue

            # Otherwise, create the link axiom from premises to conclusion
            prem_stmts = [premise_to_statement(p, id2node) for p in n.premises]
            prem_forms: list[Formula] = []
            for s in prem_stmts:
                # This shouldn't happen anymore but keep as safety
                if isinstance(s, Statement) and s.text.startswith("<rule:"):
                    continue  # Skip rule refs
                else:
                    prem_forms.append(stmt_to_formula(s))

            if prem_forms:  # Only create link if we have actual premises
                prem = _conj(prem_forms) if len(prem_forms)>1 else prem_forms[0]
                concl = stmt_to_formula(n.conclusion)
                # Quantify over free variables in premises and conclusion
                vars_p = set()
                for s in prem_stmts:
                    if isinstance(s, Statement):
                        vars_p |= _vars_in_stmt(s)
                vars_c = _vars_in_stmt(n.conclusion)
                core = Implies(prem, concl)
                core = _forall_wrap(vars_p | vars_c, core)
                out.append((f"node_{n.id}_link", fof(f"node_{n.id}_link", "axiom", core)))
    chosen = choose_goal_node(u, goal_id=goal_id)
    if chosen:
        g = id2node.get(chosen)
        if g and g.conclusion:
            out.append(("goal", fof("goal", "conjecture", stmt_to_formula(g.conclusion))))
    return out
