from __future__ import annotations
from typing import List, Set, Tuple, Optional, Dict, Any
import uuid
import networkx as nx
from .repair_types import Issue
from .core.model import ARGIR, InferenceStep, NodeRef
from .semantics import af_clingo
from .semantics.clingo_helpers import quote_id
from .fol.eprover import call_eprover


def diagnose(
    argir_obj: dict,
    goal_id: Optional[str] = None,
    semantics: str = "grounded",
    eprover_path: Optional[str] = None
) -> List[Issue]:
    """
    Main diagnostic function that detects issues in the ARGIR graph.
    """
    issues = []
    argir = ARGIR.model_validate(argir_obj)

    # 1) Detect unsupported inferences
    issues.extend(detect_unsupported_inferences(argir, semantics, eprover_path))

    # 2) Detect circular support
    issues.extend(detect_circular_support(argir))

    # 3) Detect unresolved contradictions
    issues.extend(detect_contradictions(argir, goal_id, semantics))

    # 4) Detect weak scheme instantiations
    issues.extend(detect_weak_schemes(argir))

    # 5) Check if goal is unreachable
    # But only if it's not already identified as unsupported
    if goal_id:
        unsupported_goals = {issue.target_node_ids[0] for issue in issues
                            if issue.type == "unsupported_inference" and issue.target_node_ids}

        if goal_id not in unsupported_goals and not is_goal_accepted(argir, goal_id, semantics):
            issues.append(Issue(
                id=f"I-{len(issues)+1:03d}",
                type="goal_unreachable",
                target_node_ids=[goal_id],
                evidence={"semantics": semantics, "goal_not_in_extension": True},
                detector_name="goal_reachability",
                notes=f"Goal {goal_id} is not accepted under {semantics} semantics"
            ))

    return issues


def detect_unsupported_inferences(
    argir: ARGIR,
    semantics: str = "grounded",
    eprover_path: Optional[str] = None
) -> List[Issue]:
    """
    Detect inference nodes whose conclusions are not supported by their premises.
    """
    issues = []
    issue_count = 0

    for node in argir.graph.nodes:
        if not node.conclusion:
            continue

        # Check if premises entail conclusion
        is_supported = check_inference_support(node, argir, eprover_path)

        # Also check AF acceptance
        af_accepted = is_node_accepted_in_af(argir, node.id, semantics)

        # Check for support in two ways:
        # 1. Explicit premises in the node
        has_premises = len(node.premises) > 0

        # 2. Incoming support edges
        has_support_edges = any(
            edge.target == node.id and edge.kind == "support"
            for edge in argir.graph.edges
        )

        # Node has support if it has either premises OR incoming support edges
        has_support = has_premises or has_support_edges

        # An inference is unsupported if:
        # 1. It has no support (neither premises nor incoming edges)
        # 2. The premises don't support the conclusion (if premises exist)
        if not has_support or (has_premises and not is_supported):
            issue_count += 1
            issues.append(Issue(
                id=f"I-{issue_count:03d}",
                type="unsupported_inference",
                target_node_ids=[node.id],
                evidence={
                    "premises": [p.model_dump() for p in node.premises] if node.premises else [],
                    "conclusion": node.conclusion.model_dump() if node.conclusion else None,
                    "af_rejected": not af_accepted,
                    "fol_check_failed": not is_supported,
                    "no_premises": not has_premises,
                    "has_support_edges": has_support_edges,
                    "no_support": not has_support
                },
                detector_name="inference_support",
                notes=f"Inference {node.id} lacks support: {'no support (neither premises nor incoming edges)' if not has_support else 'premises do not entail conclusion'}"
            ))

    return issues


def detect_circular_support(argir: ARGIR) -> List[Issue]:
    """
    Detect cycles in the support/derivation graph.
    """
    issues = []

    # Build support graph
    G = nx.DiGraph()
    for edge in argir.graph.edges:
        if edge.kind == "support":
            G.add_edge(edge.source, edge.target)

    # Add premise references as support edges
    for node in argir.graph.nodes:
        for premise in node.premises:
            if isinstance(premise, NodeRef):
                G.add_edge(premise.ref, node.id)

    # Find cycles
    try:
        cycles = list(nx.simple_cycles(G))
        for cycle in cycles:
            if len(cycle) > 1:  # Non-trivial cycle
                cycle_path = " → ".join(cycle + [cycle[0]])
                issues.append(Issue(
                    id=f"I-{len(issues)+1:03d}",
                    type="circular_support",
                    target_node_ids=cycle,
                    evidence={"cycle_path": cycle_path, "nodes_in_cycle": cycle},
                    detector_name="cycle_detection",
                    notes=f"Circular dependency detected: {cycle_path}"
                ))
    except:
        pass  # No cycles found

    return issues


def detect_contradictions(
    argir: ARGIR,
    goal_id: Optional[str],
    semantics: str = "grounded"
) -> List[Issue]:
    """
    Detect unresolved contradictions between nodes.
    """
    issues = []
    issue_count = 0

    # Check all nodes for contradicting atoms, not just accepted ones
    atom_map = {}  # pred_name -> [(node_id, polarity, atoms)]

    for node in argir.graph.nodes:
        if node.conclusion:
            for atom in node.conclusion.atoms:
                key = atom.pred
                if key not in atom_map:
                    atom_map[key] = []
                atom_map[key].append((node.id, atom.negated, atom))

    # Find contradictions
    for pred, occurrences in atom_map.items():
        for i, (node1, neg1, atom1) in enumerate(occurrences):
            for node2, neg2, atom2 in occurrences[i+1:]:
                # Check if they contradict (opposite polarity)
                if neg1 != neg2 and atoms_unifiable(atom1, atom2):
                    issue_count += 1
                    issues.append(Issue(
                        id=f"I-{issue_count:03d}",
                        type="contradiction_unresolved",
                        target_node_ids=[node1, node2],
                        evidence={
                            "conflicting_atoms": [
                                {"node": node1, "atom": atom1.model_dump()},
                                {"node": node2, "atom": atom2.model_dump()}
                            ],
                            "contradiction": True
                        },
                        detector_name="contradiction_detection",
                        notes=f"Nodes {node1} and {node2} have contradictory conclusions"
                    ))

    # Check explicit attacks that represent contradictions
    for edge in argir.graph.edges:
        if edge.kind == "attack":
            # Check if this is a mutual attack (contradiction)
            reverse_attack = any(
                e.source == edge.target and e.target == edge.source and e.kind == "attack"
                for e in argir.graph.edges
            )
            if reverse_attack:
                # Only report once for mutual attacks
                if edge.source < edge.target:  # Lexicographic ordering to avoid duplicates
                    issue_count += 1
                    issues.append(Issue(
                        id=f"I-{issue_count:03d}",
                        type="contradiction_unresolved",
                        target_node_ids=[edge.source, edge.target],
                        evidence={
                            "mutual_attacks": True,
                            "attack_edges": [
                                edge.model_dump(),
                                {"source": edge.target, "target": edge.source, "kind": "attack"}
                            ]
                        },
                        detector_name="mutual_attack_detection",
                        notes=f"Nodes {edge.source} and {edge.target} attack each other (contradiction)"
                    ))

    return issues


def detect_weak_schemes(argir: ARGIR) -> List[Issue]:
    """
    Detect weak scheme instantiations based on critical questions.
    """
    issues = []

    # Critical questions per scheme type
    critical_questions = {
        "causal": ["Is there evidence for the causal link?", "Are there confounding factors?"],
        "authority": ["Is the authority credible?", "Is this within the authority's domain?"],
        "analogy": ["Are the cases sufficiently similar?", "Are there relevant differences?"],
        "example": ["Is the example representative?", "Are there counter-examples?"]
    }

    for node in argir.graph.nodes:
        if node.rule and node.rule.scheme:
            scheme = node.rule.scheme
            if scheme in critical_questions:
                # Check if critical questions are addressed
                missing_cqs = []

                # Simple heuristic: check if premises address critical questions
                premise_texts = []
                for p in node.premises:
                    if hasattr(p, 'text'):
                        premise_texts.append(p.text.lower())

                cqs = critical_questions[scheme]
                for cq in cqs:
                    # Very basic check - in real implementation, use more sophisticated matching
                    addressed = any(
                        keyword in ' '.join(premise_texts)
                        for keyword in ['evidence', 'study', 'expert', 'similar', 'difference']
                    )
                    if not addressed:
                        missing_cqs.append(cq)

                if missing_cqs:
                    issues.append(Issue(
                        id=f"I-{len(issues)+1:03d}",
                        type="weak_scheme_instantiation",
                        target_node_ids=[node.id],
                        evidence={
                            "scheme": scheme,
                            "missing_critical_questions": missing_cqs,
                            "rule": node.rule.model_dump()
                        },
                        detector_name="scheme_analysis",
                        notes=f"Scheme '{scheme}' missing critical backing"
                    ))

    return issues


# Helper functions

def check_inference_support(
    node: InferenceStep,
    argir: ARGIR,
    eprover_path: Optional[str] = None
) -> bool:
    """
    Check if an inference is supported by its premises.
    """
    if not node.conclusion:
        return True

    # If E-prover is available, check FOL entailment
    if eprover_path and argir.metadata.get("fol"):
        # This would need the actual TPTP generation logic
        # For now, return a placeholder
        return False

    # Basic check: at least one premise must be present
    return len(node.premises) > 0


def is_node_accepted_in_af(argir: ARGIR, node_id: str, semantics: str) -> bool:
    """
    Check if a node is accepted under the given AF semantics.
    """
    args, atts = extract_af_args_attacks(argir)

    if semantics == "grounded":
        ext = af_clingo.grounded(args, atts)
        return node_id in ext
    elif semantics == "preferred":
        fam = af_clingo.preferred(args, atts)
        # credulous: exists a preferred extension containing the node
        return any(node_id in S for S in fam)
    elif semantics == "stable":
        fam = af_clingo.stable(args, atts)
        return any(node_id in S for S in fam)
    else:
        return False


def get_accepted_nodes(argir: ARGIR, semantics: str) -> Set[str]:
    """
    Get all accepted nodes under the given semantics.
    """
    args, atts = extract_af_args_attacks(argir)

    if semantics == "grounded":
        return set(af_clingo.grounded(args, atts))
    elif semantics == "preferred":
        # Union of all preferred extensions (useful for UI overlays)
        fam = af_clingo.preferred(args, atts)
        out: Set[str] = set()
        for S in fam:
            out |= set(S)
        return out
    elif semantics == "stable":
        fam = af_clingo.stable(args, atts)
        out: Set[str] = set()
        for S in fam:
            out |= set(S)
        return out

    return set()


def is_goal_accepted(argir: ARGIR, goal_id: str, semantics: str) -> bool:
    """
    Check if the goal is accepted under the given semantics.
    """
    return is_node_accepted_in_af(argir, goal_id, semantics)


def extract_af_facts(argir: ARGIR) -> List[str]:
    """
    Extract AF facts from ARGIR for clingo processing.
    """
    facts = []

    # Add argument facts - filter empty IR_* nodes
    for node in argir.graph.nodes:
        # Skip empty implicit rule nodes (IR_*) that have no atoms
        if _is_af_argument_node(node):
            facts.append(f"arg({quote_id(node.id)}).")

    # Add attack facts
    for edge in argir.graph.edges:
        if edge.kind == "attack":
            # Only add attacks between actual AF arguments
            if _has_af_argument(argir, edge.source) and _has_af_argument(argir, edge.target):
                facts.append(f"att({quote_id(edge.source)},{quote_id(edge.target)}).")

    return facts


def extract_af_args_attacks(argir: ARGIR) -> Tuple[List[str], Set[Tuple[str, str]]]:
    """
    Extract arguments and attacks from ARGIR for af_clingo functions.
    """
    # Filter empty IR_* nodes
    args = [node.id for node in argir.graph.nodes if _is_af_argument_node(node)]
    atts = set()

    for edge in argir.graph.edges:
        if edge.kind == "attack":
            # Only add attacks between actual AF arguments
            if _has_af_argument(argir, edge.source) and _has_af_argument(argir, edge.target):
                atts.add((edge.source, edge.target))

    return args, atts


def atoms_unifiable(atom1, atom2) -> bool:
    """
    Check if two atoms are unifiable (same predicate and arity).
    """
    return (atom1.pred == atom2.pred and
            len(atom1.args) == len(atom2.args))


def _is_af_argument_node(node: InferenceStep) -> bool:
    """
    Check if a node should be an AF argument.
    Filter empty IR_* nodes that have no atoms in conclusion.
    """
    # Implicit rule nodes without atoms are not AF arguments
    if node.id.startswith("IR_"):
        # Check if it has atoms in conclusion
        if not node.conclusion or not node.conclusion.atoms:
            return False
    return True


def _has_af_argument(argir: ARGIR, node_id: str) -> bool:
    """
    Check if a node ID corresponds to an AF argument.
    """
    node = next((n for n in argir.graph.nodes if n.id == node_id), None)
    return node is not None and _is_af_argument_node(node)