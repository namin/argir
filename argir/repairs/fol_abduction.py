# argir/repairs/fol_abduction.py
from __future__ import annotations
from typing import List, Tuple, Dict, Optional
import uuid, copy

from ..repair_types import Issue, Repair, Patch, Verification
from ..core.model import ARGIR, InferenceStep, Statement, Atom, Term, Edge
from ..fol.translate import argir_to_fof
from ..fol.eprover import call_eprover

# ---------- public API ----------

def abduce_missing_premises(
    argir_data: dict,
    issue: Issue,
    max_atoms: int = 2,
    timeout: float = 2.0,
    eprover_path: Optional[str] = None  # if your call_eprover needs it, thread it through
) -> List[Repair]:
    """Deterministic, exporter-backed, proof-verified abduction."""
    if issue.type not in {"unsupported_inference", "weak_scheme_instantiation"}:
        return []

    argir = ARGIR.model_validate(argir_data)
    if not issue.target_node_ids:
        return []
    target_id = issue.target_node_ids[0]
    target = _get_node(argir, target_id)
    if not target or not target.conclusion:
        return []

    pred_sigs, consts = _collect_signature(argir)
    anchors = _constants_in_target(target)

    # Build TPTP once (rules + facts, separate goal)
    try:
        fof_pairs = argir_to_fof(argir, fol_mode="classical", goal_id=target_id)
    except Exception:
        # If FOL export fails, return empty
        return []

    axioms = [s for (n, s) in fof_pairs if n != "goal"]
    goal = next((s for (n, s) in fof_pairs if n == "goal"), None)
    if not goal:
        return []

    # Enumerate hypotheses deterministically
    hyps = _enumerate_candidates(pred_sigs, consts, anchors, max_atoms=max_atoms)

    repairs: List[Repair] = []
    for atoms in hyps:
        proved, ms, consistent = _prove(axioms, goal, atoms, timeout, eprover_path)
        if not proved or not consistent:
            continue
        # Check for minimality
        atoms = _irredundant_minimal(axioms, goal, atoms, timeout)
        patch = _make_patch(target, atoms)

        # Comprehensive AF verification: check both target (repaired node) and goal
        from ..diagnostics import is_node_accepted_in_af
        af_semantics = "grounded"

        # Before patch: check current AF status
        target_before = bool(is_node_accepted_in_af(argir, target_id, af_semantics))

        # After patch: check AF status for target
        patched_argir = _apply_patch(copy.deepcopy(argir), patch)
        target_after = bool(is_node_accepted_in_af(patched_argir, target_id, af_semantics))

        # Also check goal if it's different from target
        goal_id = (argir.metadata or {}).get("goal_id")
        goal_before = None
        goal_after = None
        if goal_id and goal_id != target_id:
            goal_before = bool(is_node_accepted_in_af(argir, goal_id, af_semantics))
            goal_after = bool(is_node_accepted_in_af(patched_argir, goal_id, af_semantics))

        verification = Verification(
            af_semantics=af_semantics,
            af_goal_accepted=bool(goal_after if goal_id else target_after),  # Keep for any legacy uses
            af_optimal=False,
            fol_entailed=True,
            artifacts={
                "eprover_ms": ms,
                "hypothesis_tptp": [_tptp(a) for a in atoms],
                "af_impact": {
                    "target": {
                        "id": target_id,
                        "before": target_before,
                        "after": target_after,
                        "changed": target_after != target_before
                    },
                    "goal": {
                        "id": goal_id,
                        "before": goal_before,
                        "after": goal_after,
                        "changed": (goal_after != goal_before) if goal_id else None
                    } if goal_id else None,
                    "explanation": "Support edges don't affect AF acceptance - only attacks matter"
                }
            },
        )
        repairs.append(Repair(
            id=f"ABD-{uuid.uuid4().hex[:8]}",
            issue_id=issue.id,
            kind="FOL",
            patch=patch,
            cost=len(atoms),
            verification=verification
        ))
        if len(repairs) >= 3:
            break
    return repairs

# ---------- internals ----------

def _get_node(argir: ARGIR, nid: str) -> Optional[InferenceStep]:
    return next((n for n in argir.graph.nodes if getattr(n, "id", None) == nid), None)

def _collect_signature(argir: ARGIR) -> Tuple[Dict[str,int], List[str]]:
    """Predicates->arity (deterministic) and constants seen in graph/lexicon."""
    sig: Dict[str,int] = {}
    consts: set[str] = set()
    # nodes
    for n in argir.graph.nodes:
        for stmt in ([n.conclusion] if n.conclusion else []):
            for a in (stmt.atoms or []):
                sig[a.pred] = max(sig.get(a.pred, 0), len(a.args))
                for t in a.args:
                    if getattr(t, "kind", None) == "Const":
                        consts.add(t.name)
        for p in (n.premises or []):
            # Handle both Statement and Ref types
            if hasattr(p, 'atoms'):
                for a in (p.atoms or []):
                    sig[a.pred] = max(sig.get(a.pred, 0), len(a.args))
                    for t in a.args:
                        if getattr(t, "kind", None) == "Const":
                            consts.add(t.name)
    # lexicon - try full_atom_lexicon first, then atom_lexicon
    lex = argir.metadata.get("full_atom_lexicon") or argir.metadata.get("atom_lexicon") or {}
    if isinstance(lex, dict):
        # Handle new format with predicates/constants
        if "predicates" in lex:
            for k, v in (lex.get("predicates") or {}).items():
                sig[k] = max(sig.get(k, 0), int(v))
            for c in (lex.get("constants") or []):
                consts.add(c)
        else:
            # Handle old format (simple pred -> examples)
            for k in lex:
                sig[k] = max(sig.get(k, 0), 0)
    # deterministic
    return dict(sorted(sig.items())), sorted(consts)

def _constants_in_target(target: InferenceStep) -> List[str]:
    out: list[str] = []
    if target.conclusion:
        for a in (target.conclusion.atoms or []):
            for t in a.args:
                if getattr(t, "kind", None) == "Const" and t.name not in out:
                    out.append(t.name)
    return out

def _enumerate_candidates(sig: Dict[str,int], consts: List[str], anchors: List[str], max_atoms: int) -> List[List[Atom]]:
    """1-atom anchored first; then small 2-atom combos; capped for speed."""
    singles: list[Atom] = []
    for pred, ar in sig.items():
        if ar == 0:
            singles.append(Atom(pred=pred, args=[], negated=False))
        elif ar == 1:
            for c in anchors:
                if c in consts:
                    singles.append(Atom(pred=pred, args=[Term(kind="Const", name=c)], negated=False))
            for c in consts:
                if c not in anchors:
                    singles.append(Atom(pred=pred, args=[Term(kind="Const", name=c)], negated=False))
        elif ar == 2:
            for a in anchors:
                if a in consts:
                    for b in consts:
                        singles.append(Atom(pred=pred, args=[Term(kind="Const", name=a), Term(kind="Const", name=b)], negated=False))
            for i, a in enumerate(consts):
                for b in consts:
                    singles.append(Atom(pred=pred, args=[Term(kind="Const", name=a), Term(kind="Const", name=b)], negated=False))
    singles = singles[:50]
    hyps = [[s] for s in singles]
    if max_atoms >= 2:
        K = min(20, len(singles))
        for i in range(K):
            for j in range(i+1, K):
                hyps.append([singles[i], singles[j]])
    return hyps

def _prove(axioms: List[str], goal_fof: str, atoms: List[Atom], timeout: float, eprover_path: Optional[str]) -> Tuple[bool, int, bool]:
    hyp_fof = [_fof_axiom(f"h{i+1}", _tptp(a)) for i, a in enumerate(atoms)]
    problem = axioms + hyp_fof + [goal_fof]
    res = call_eprover(problem, time_limit=int(timeout))
    proved = bool(res.get("theorem") or res.get("unsat"))
    # consistency guard: try to prove $false as conjecture
    false_prob = axioms + hyp_fof + ["fof(cnt, conjecture, $false)."]
    cres = call_eprover(false_prob, time_limit=int(timeout))
    inconsistent = bool(cres.get("theorem") or cres.get("unsat"))
    ms = _extract_ms(res.get("raw", "") + "\n" + str(res))
    return proved, ms, (not inconsistent)

def _extract_ms(raw: str) -> int:
    # Best-effort; leave 0 if not parseable
    return 0


def _irredundant_minimal(axioms: list[str], goal: str, hyp_atoms: list[Atom], timeout: float) -> list[Atom]:
    """Check if a smaller subset of the hypothesis suffices to prove the goal."""
    if len(hyp_atoms) <= 1:
        return hyp_atoms
    from itertools import combinations
    best = hyp_atoms
    for k in range(1, len(hyp_atoms)):
        for sub in combinations(hyp_atoms, k):
            proved, _, consistent = _prove(axioms, goal, list(sub), timeout, None)
            if proved and consistent:
                return list(sub)  # immediate return on first smaller success
    return best

def _tptp(a: Atom) -> str:
    if a.args:
        args = ",".join(t.name for t in a.args)
        s = f"{a.pred}({args})"
    else:
        s = a.pred
    return f"~({s})" if a.negated else s

def _fof_axiom(name: str, atom: str) -> str:
    return f"fof({name}, axiom, {atom})."

def _make_patch(target: InferenceStep, atoms: List[Atom]) -> Patch:
    patch = Patch()
    # Create a more descriptive ID based on the predicate names
    pred_names = "_".join(a.pred[:8] for a in atoms[:2])  # First 2 preds, max 8 chars each
    if not pred_names:
        pred_names = "hyp"
    pid = f"P_{pred_names}_{uuid.uuid4().hex[:4]}"
    patch.add_nodes.append({
        "id": pid,
        "kind": "Premise",
        "atoms": [a.model_dump() for a in atoms],
        "text": " and ".join(_tptp(a) for a in atoms),
        "rationale": "Added by abduction to support inference"
    })
    patch.add_edges.append({"source": pid, "target": target.id, "kind": "support"})
    for a in atoms:
        patch.fol_hypotheses.append(_tptp(a))
    return patch


def _apply_patch(argir: ARGIR, patch: Patch) -> ARGIR:
    # add nodes
    for n in patch.add_nodes:
        atoms = [Atom(**a) for a in (n.get("atoms") or [])]
        text = n.get("text", " and ".join(_tptp(a) for a in atoms))
        argir.graph.nodes.append(InferenceStep(id=n["id"], premises=[], conclusion=Statement(atoms=atoms, text=text)))
    # add edges
    for e in patch.add_edges:
        argir.graph.edges.append(Edge(source=e["source"], target=e["target"], kind="support"))
    return argir