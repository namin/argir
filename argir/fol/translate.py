from __future__ import annotations
from typing import List, Tuple, Optional
import re
from .ast import Atom, Pred, Var, Const, Forall, Exists, Not, And, Or, Implies, Formula, Term
from ..core.model import ARGIR, Statement, NodeRef, InferenceStep

# Variable name pattern for salvaging variables in strict mode
VAR_NAME_RE = re.compile(r'^[XYZWUV]\d*$')  # X, Y, Z, W, U, V with optional digits

# TPTP token sanitization
_TPTP_IDENT_RE = re.compile(r"^[a-z][A-Za-z0-9_]*$")        # functor/predicate symbol
_TPTP_VAR_RE   = re.compile(r"^[A-Z][A-Za-z0-9_]*$")        # variable symbol

def _sanitize_symbol(s: str, *, is_var: bool=False) -> str:
    """Return a TPTP-safe symbol (quoted if necessary)."""
    if s is None:
        return s
    s = str(s)
    # quick fixups: replace disallowed chars
    s = s.replace("-", "_").replace(" ", "_").replace("/", "_").replace(".", "_")
    if is_var:
        # variables must start uppercase; if not, promote
        if not _TPTP_VAR_RE.match(s):
            if s and s[0].islower():
                s = s[0].upper() + s[1:]
            if not _TPTP_VAR_RE.match(s):
                s = "V_" + re.sub(r"[^A-Za-z0-9_]", "_", s)
        return s
    else:
        # predicates/functions must start lowercase; if not, demote or quote
        if _TPTP_IDENT_RE.match(s):
            return s
        # Try to demote leading uppercase
        if s and s[0].isupper():
            s = s[0].lower() + s[1:]
        s = re.sub(r"[^A-Za-z0-9_]", "_", s)
        if not _TPTP_IDENT_RE.match(s):
            # Final fallback: single-quote the whole thing (TPTP allows quoted atoms)
            return f"'{s}'"
        return s


def validate_tptp(fof_lines: list[str]) -> tuple[bool, str]:
    """Quick preflight: ensure every line ends with '.', and attempt parsing via E-prover in parse-only mode."""
    text = "\n".join(l if l.strip().endswith(".") else f"{l.rstrip('.')}." for l in fof_lines)
    try:
        import subprocess, tempfile, shutil
        eprover = shutil.which("eprover")
        if not eprover:
            return True, ""  # Skip validation if E-prover not available

        with tempfile.NamedTemporaryFile("w", suffix=".p", delete=False) as f:
            f.write(text)
            f.flush()
            # '--parse-only' is supported by E; if absent in your version, use '--proof-object=none --cpu-limit=1'
            res = subprocess.run(["eprover", "--parse-only", f.name],
                                 capture_output=True, text=True, timeout=2)
        ok = res.returncode == 0 and "SZS status" in (res.stdout + res.stderr)
        return ok, text if not ok else ""
    except Exception as ex:
        # If E isn't available, skip validation; the main call will mark unverified
        return True, ""

def _to_term(t):
    """Convert term dict to FOL Term, with variable salvage for strict mode."""
    name = t.name
    kind = getattr(t, "kind", None) if hasattr(t, "kind") else t.get("kind")
    # If explicitly marked as Var, or matches our variable pattern, treat as variable
    if kind == "Var" or VAR_NAME_RE.match(name):
        return Var(_sanitize_symbol(name, is_var=True))
    return Const(_sanitize_symbol(name, is_var=False))

def _to_atom(a):
    pred_name = _sanitize_symbol(a.pred, is_var=False)
    return Atom(Pred(pred_name, len(a.args)), [_to_term(x) for x in a.args], a.negated)

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
    elif isinstance(f, And) or isinstance(f, Or) or isinstance(f, Implies):
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
    # 1) Build conjunction of atoms
    if s.atoms:
        phi: Formula = _to_atom(s.atoms[0])
        for a in s.atoms[1:]:
            phi = And(phi, _to_atom(a))
    else:
        return Atom(Pred("nl_"+(s.text[:20].strip().replace(" ","_") or "stmt"), 0), [])

    # 2) Apply quantifiers from s.quantifiers (outermost first)
    # Supports both soft format {"kind":"forall","vars":["X"]} and
    # strict format {"kind":"forall","var":"X"} as well as Quantifier objects
    qs = getattr(s, "quantifiers", None) or []
    for q in reversed(qs):  # wrap inside-out: last listed is innermost
        if isinstance(q, dict):
            kind = q.get("kind")
            # Handle both "var" (strict ARGIR) and "vars" (soft format)
            if "var" in q:
                vars_ = [q["var"]]
            elif "vars" in q:
                vars_ = q.get("vars", [])
            else:
                vars_ = []
        elif hasattr(q, "kind") and hasattr(q, "var"):
            # Handle Quantifier objects from strict ARGIR
            kind = q.kind
            vars_ = [q.var]
        else:
            # Accept "forall X", "exists X" as a fallback
            parts = str(q).split()
            kind = parts[0].lower() if parts else None
            vars_ = [parts[1]] if len(parts) > 1 else []

        for v in reversed(vars_):
            if kind == "forall":
                phi = Forall(Var(v), phi)
            elif kind == "exists":
                phi = Exists(Var(v), phi)
            # else: ignore unknown

    return phi

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
        excs = [stmt_to_formula(s) for s in n.rule.exceptions]
        for s in n.rule.exceptions:
            all_vars |= _vars_in_stmt(s)
        if ants and cons:
            # Build antecedent with negated exceptions: A1 ∧ ... ∧ ¬E1 ∧ ¬E2 ∧ ...
            # This means: the rule applies ONLY when NO exception holds
            if excs:
                neg_excs = [Not(e) for e in excs]  # Negate EACH exception individually
                ante = _conj(ants + neg_excs)
            else:
                ante = _conj(ants) if len(ants) > 1 else ants[0]
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
    # Guard against empty atom lists (all([]) == True)
    return bool(s.atoms) and all(len(a.args) == 0 for a in s.atoms)


def choose_goal_node(u: ARGIR, goal_id: Optional[str] = None) -> Optional[str]:
    """Choose goal node with improved heuristics:
    1. Use explicit goal_id if provided
    2. Check metadata.goal_id from LLM
    3. Prefer conclusions with variables (quantified forms)
    4. De-prioritize 0-arity "macro" predicates
    5. Find nodes that are not referenced as premises (inference sinks)
    6. Prefer nodes with more complex derivations (have premises)
    """
    if goal_id:
        return goal_id

    # Check if LLM provided a goal_id in metadata
    if hasattr(u, 'metadata') and isinstance(u.metadata, dict):
        llm_goal = u.metadata.get('goal_id')
        if llm_goal:
            return llm_goal

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

    # Collect what conclusions are derived (by formula text)
    concluded_stmts = set()
    for n in u.graph.nodes:
        if n.conclusion:
            concluded_stmts.add(formula(stmt_to_formula(n.conclusion)))

    # Compute incoming support indegrees per node
    in_support: dict[str,int] = {n.id: 0 for n in u.graph.nodes}
    for e in u.graph.edges:
        if e.kind == "support" and e.target in in_support:
            in_support[e.target] += 1

    # Pre-pick goal (so we can avoid exporting it as a fact)
    chosen = choose_goal_node(u, goal_id=goal_id)
    goal_formula_str = None
    if chosen:
        g = id2node.get(chosen)
        if g and g.conclusion:
            goal_formula_str = formula(stmt_to_formula(g.conclusion))
        elif g and g.rule:
            goal_formula_str = formula(rule_to_formula(g, fol_mode=fol_mode))

    # Export GIVEN facts as axioms of their conclusions (not rules)
    for n in u.graph.nodes:
        if n.rule and (n.rule.name or "").lower() == "given" and n.conclusion:
            phi = stmt_to_formula(n.conclusion)
            out.append((f"prem_{n.id}", fof(f"prem_{n.id}", "axiom", phi)))

    # Export rules (including implicit rules IR_*) EXCEPT 'Given'
    for n in u.graph.nodes:
        if n.rule and (n.rule.name or "").lower() != "given":
            # Ensure implicit rules are properly exported for abduction
            rule_formula = rule_to_formula(n, fol_mode=fol_mode)
            out.append((f"rule_{n.id}", fof(f"rule_{n.id}", "axiom", rule_formula)))

    # Export premise-only nodes (old behavior)
    for n in u.graph.nodes:
        if not n.rule and not n.conclusion and n.premises:
            for i, p in enumerate(n.premises):
                if isinstance(p, Statement):
                    out.append((f"prem_{n.id}_{i}", fof(f"prem_{n.id}_{i}", "axiom", stmt_to_formula(p))))

    # Export fact nodes: ONLY those with no rule, no inline premises,
    # AND no incoming support edges, AND not equal to the goal
    for n in u.graph.nodes:
        if not n.rule and not n.premises and n.conclusion and in_support.get(n.id, 0) == 0:
            fact_formula = stmt_to_formula(n.conclusion)
            # Quantify over any free variables in facts
            fact_vars = _vars_in_stmt(n.conclusion)
            if fact_vars:
                fact_formula = _forall_wrap(fact_vars, fact_formula)
            fact_str = formula(fact_formula)
            if goal_formula_str is None or fact_str != goal_formula_str:
                out.append((f"fact_{n.id}", fof(f"fact_{n.id}", "axiom", fact_formula)))

    # NEW: Export orphan premises as facts (resolve NodeRef -> Statement)
    # These are statement premises that aren't concluded anywhere
    orphan_facts = set()
    orphan_counter = 0
    for n in u.graph.nodes:
        for p in n.premises:
            s = premise_to_statement(p, id2node)  # resolve NodeRef
            if not isinstance(s, Statement):
                continue
            # Skip rule references; those are exported via the rule pass
            if (s.text or "").startswith("<rule:"):
                continue

            stmt_formula = stmt_to_formula(s)
            stmt_key = formula(stmt_formula)
            if stmt_key not in concluded_stmts and stmt_key not in orphan_facts:
                orphan_facts.add(stmt_key)
                orphan_counter += 1
                # Quantify over any free variables in orphan facts
                orphan_vars = _vars_in_stmt(s)
                if orphan_vars:
                    stmt_formula = _forall_wrap(orphan_vars, stmt_formula)
                stmt_str = formula(stmt_formula)
                if goal_formula_str is None or stmt_str != goal_formula_str:
                    out.append((f"orphan_fact_{orphan_counter}",
                              fof(f"orphan_fact_{orphan_counter}", "axiom", stmt_formula)))
    # Inference-node linkage axioms removed to prevent vacuous proofs
    # These were axioms of the form: premises => conclusion for any node with both
    # They allowed proofs to bypass the actual logical rules
    # ---------- Goal ----------
    if chosen:
        g = id2node.get(chosen)
        if g and g.conclusion:
            out.append(("goal", fof("goal", "conjecture", stmt_to_formula(g.conclusion))))
        elif g and g.rule:
            # If the chosen node has no conclusion but has a rule, use the rule as the goal
            out.append(("goal", fof("goal", "conjecture", rule_to_formula(g, fol_mode=fol_mode))))
    return out
