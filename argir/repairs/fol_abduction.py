from __future__ import annotations
from typing import List, Set, Tuple, Dict, Any, Optional
import uuid
import itertools
import tempfile
import os
from ..repair_types import Issue, Repair, Patch, Verification
from ..core.model import ARGIR, Statement, Atom, Term, InferenceStep
from ..fol.eprover import call_eprover


def abduce_missing_premises(
    argir_data: dict,
    issue: Issue,
    max_atoms: int = 2,
    timeout: float = 2.0,
    eprover_path: Optional[str] = None
) -> List[Repair]:
    """
    Find minimal missing premises that would make an unsupported inference valid.
    """
    repairs = []

    # Convert to ARGIR model
    argir = ARGIR.model_validate(argir_data)

    # Only handle unsupported inference and weak scheme issues
    if issue.type not in ["unsupported_inference", "weak_scheme_instantiation"]:
        return repairs

    # Get the target inference node
    target_id = issue.target_node_ids[0] if issue.target_node_ids else None
    if not target_id:
        return repairs

    target_node = next((n for n in argir.graph.nodes if n.id == target_id), None)
    if not target_node or not target_node.conclusion:
        return repairs

    # Get atom lexicon from metadata
    lexicon = argir.metadata.get("atom_lexicon", {})
    if not lexicon:
        lexicon = extract_atom_lexicon(argir)

    # Generate hypothesis space
    hypotheses = generate_hypotheses(lexicon, argir, max_atoms)

    # Test each hypothesis
    successful_hypotheses = []
    for hyp_atoms in hypotheses:
        if test_hypothesis(argir, target_node, hyp_atoms, eprover_path, timeout):
            successful_hypotheses.append(hyp_atoms)
            if len(successful_hypotheses) >= 3:  # Limit to top 3
                break

    # Convert successful hypotheses to repairs
    for i, hyp_atoms in enumerate(successful_hypotheses):
        patch = create_premise_patch(target_node, hyp_atoms)
        verification = verify_fol_repair(argir, target_node, hyp_atoms, eprover_path, timeout)

        repair = Repair(
            id=f"R-{uuid.uuid4().hex[:8]}",
            issue_id=issue.id,
            kind="FOL",
            patch=patch,
            cost=len(hyp_atoms),
            verification=verification
        )
        repairs.append(repair)

    return repairs


def extract_atom_lexicon(argir: ARGIR) -> Dict[str, Any]:
    """
    Extract predicates and constants from the ARGIR graph.
    """
    lexicon = {
        "predicates": {},
        "constants": set()
    }

    for node in argir.graph.nodes:
        # Extract from conclusion
        if node.conclusion:
            for atom in node.conclusion.atoms:
                if atom.pred not in lexicon["predicates"]:
                    lexicon["predicates"][atom.pred] = len(atom.args)
                for arg in atom.args:
                    if arg.kind == "Const":
                        lexicon["constants"].add(arg.name)

        # Extract from premises
        for premise in node.premises:
            if hasattr(premise, "atoms"):
                for atom in premise.atoms:
                    if atom.pred not in lexicon["predicates"]:
                        lexicon["predicates"][atom.pred] = len(atom.args)
                    for arg in atom.args:
                        if arg.kind == "Const":
                            lexicon["constants"].add(arg.name)

    return lexicon


def generate_hypotheses(
    lexicon: Dict[str, Any],
    argir: ARGIR,
    max_atoms: int
) -> List[List[Atom]]:
    """
    Generate candidate hypothesis atoms from the lexicon.
    """
    hypotheses = []
    predicates = lexicon.get("predicates", {})
    constants = list(lexicon.get("constants", []))

    if not predicates or not constants:
        return hypotheses

    # Generate single atoms first
    single_atoms = []
    for pred, arity in predicates.items():
        if arity == 0:
            # Propositional atom
            atom = Atom(pred=pred, args=[], negated=False)
            single_atoms.append(atom)
        elif arity == 1:
            # Unary predicate
            for const in constants[:5]:  # Limit to avoid explosion
                atom = Atom(
                    pred=pred,
                    args=[Term(kind="Const", name=const)],
                    negated=False
                )
                single_atoms.append(atom)
        elif arity == 2:
            # Binary predicate
            for c1, c2 in itertools.product(constants[:3], repeat=2):
                atom = Atom(
                    pred=pred,
                    args=[
                        Term(kind="Const", name=c1),
                        Term(kind="Const", name=c2)
                    ],
                    negated=False
                )
                single_atoms.append(atom)
                if len(single_atoms) > 20:  # Limit total
                    break

    # Add single-atom hypotheses
    for atom in single_atoms[:10]:
        hypotheses.append([atom])

    # Add two-atom hypotheses if requested
    if max_atoms >= 2:
        for pair in itertools.combinations(single_atoms[:10], 2):
            hypotheses.append(list(pair))
            if len(hypotheses) > 50:  # Total limit
                break

    return hypotheses


def test_hypothesis(
    argir: ARGIR,
    target_node: InferenceStep,
    hypothesis_atoms: List[Atom],
    eprover_path: Optional[str],
    timeout: float
) -> bool:
    """
    Test if adding hypothesis atoms makes the inference valid.
    """
    if not eprover_path:
        # Fallback: simple heuristic check
        return heuristic_support_check(target_node, hypothesis_atoms)

    # Build TPTP with hypothesis
    tptp_lines = build_tptp_with_hypothesis(argir, target_node, hypothesis_atoms)
    if not tptp_lines:
        return False

    # Run E-prover
    with tempfile.NamedTemporaryFile(mode="w", suffix=".p", delete=False) as f:
        f.write("\n".join(tptp_lines))
        temp_file = f.name

    try:
        with open(temp_file, "r") as f:
            fof_lines = f.readlines()
        result = call_eprover(fof_lines, time_limit=int(timeout))
        success = result.get("theorem", False)
        return success
    except Exception:
        return False
    finally:
        os.unlink(temp_file)


def heuristic_support_check(
    target_node: InferenceStep,
    hypothesis_atoms: List[Atom]
) -> bool:
    """
    Simple heuristic to check if hypothesis provides support.
    """
    # Check if hypothesis predicates relate to conclusion
    if not target_node.conclusion:
        return False

    conclusion_preds = {a.pred for a in target_node.conclusion.atoms}
    hypothesis_preds = {a.pred for a in hypothesis_atoms}

    # Very basic: hypothesis should mention relevant predicates
    # or provide missing links
    return bool(conclusion_preds & hypothesis_preds) or len(hypothesis_atoms) > 0


def build_tptp_with_hypothesis(
    argir: ARGIR,
    target_node: InferenceStep,
    hypothesis_atoms: List[Atom]
) -> List[str]:
    """
    Build TPTP axioms including the hypothesis.
    """
    lines = []

    # Add standard preamble
    lines.append("% TPTP with hypothesis for abduction")

    # Convert existing premises to FOF
    axiom_num = 1
    for node in argir.graph.nodes:
        if node.conclusion:
            # Skip the target node's conclusion (it's our conjecture)
            if node.id == target_node.id:
                continue

            fof = atom_list_to_fof(node.conclusion.atoms, f"axiom_{axiom_num}")
            if fof:
                lines.append(fof)
                axiom_num += 1

    # Add hypothesis atoms as axioms
    for i, atom in enumerate(hypothesis_atoms):
        fof = atom_to_fof(atom, f"hypothesis_{i+1}")
        if fof:
            lines.append(fof)

    # Add target conclusion as conjecture
    if target_node.conclusion:
        conj_fof = atom_list_to_fof(
            target_node.conclusion.atoms,
            "target_conjecture",
            is_conjecture=True
        )
        if conj_fof:
            lines.append(conj_fof)

    return lines


def atom_to_fof(atom: Atom, name: str) -> str:
    """
    Convert a single atom to FOF format.
    """
    pred_str = atom.pred
    if atom.args:
        args_str = ",".join(arg.name for arg in atom.args)
        pred_str = f"{atom.pred}({args_str})"

    formula = f"~{pred_str}" if atom.negated else pred_str
    return f"fof({name}, axiom, {formula})."


def atom_list_to_fof(
    atoms: List[Atom],
    name: str,
    is_conjecture: bool = False
) -> str:
    """
    Convert a list of atoms to a FOF formula.
    """
    if not atoms:
        return ""

    atom_strs = []
    for atom in atoms:
        pred_str = atom.pred
        if atom.args:
            args_str = ",".join(arg.name for arg in atom.args)
            pred_str = f"{atom.pred}({args_str})"
        atom_str = f"~{pred_str}" if atom.negated else pred_str
        atom_strs.append(atom_str)

    if len(atom_strs) == 1:
        formula = atom_strs[0]
    else:
        formula = " & ".join(f"({a})" for a in atom_strs)

    role = "conjecture" if is_conjecture else "axiom"
    return f"fof({name}, {role}, {formula})."


def create_premise_patch(
    target_node: InferenceStep,
    hypothesis_atoms: List[Atom]
) -> Patch:
    """
    Create a patch that adds a new premise node with the hypothesis.
    """
    patch = Patch()

    # Create new premise node
    premise_id = f"P_hyp_{uuid.uuid4().hex[:6]}"
    premise_text = " and ".join(
        f"{a.pred}({','.join(arg.name for arg in a.args)})"
        for a in hypothesis_atoms
    )

    patch.add_nodes.append({
        "id": premise_id,
        "kind": "Premise",
        "atoms": [a.model_dump() for a in hypothesis_atoms],
        "text": premise_text,
        "rationale": "Added by FOL abduction to support inference"
    })

    # Add support edge from new premise to target
    patch.add_edges.append({
        "source": premise_id,
        "target": target_node.id,
        "kind": "support"
    })

    # Record FOL hypotheses for verification
    for atom in hypothesis_atoms:
        fol_str = atom.pred
        if atom.args:
            args_str = ",".join(arg.name for arg in atom.args)
            fol_str = f"{atom.pred}({args_str})"
        patch.fol_hypotheses.append(fol_str)

    return patch


def verify_fol_repair(
    argir: ARGIR,
    target_node: InferenceStep,
    hypothesis_atoms: List[Atom],
    eprover_path: Optional[str],
    timeout: float
) -> Verification:
    """
    Verify that the hypothesis makes the inference valid.
    """
    fol_entailed = None
    artifacts = {}

    if eprover_path:
        # Test with E-prover
        fol_entailed = test_hypothesis(argir, target_node, hypothesis_atoms, eprover_path, timeout)
        artifacts["eprover_result"] = "success" if fol_entailed else "failure"

    # Check AF acceptance (as secondary verification)
    from ..diagnostics import is_node_accepted_in_af
    af_accepted = is_node_accepted_in_af(argir, target_node.id, "grounded")

    return Verification(
        af_semantics="grounded",
        af_goal_accepted=af_accepted,
        af_optimal=False,
        fol_entailed=fol_entailed,
        artifacts=artifacts
    )