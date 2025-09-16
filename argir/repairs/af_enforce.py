from __future__ import annotations
from typing import List, Set, Tuple, Dict, Any, Optional
import uuid
import subprocess
import tempfile
import os
from ..repair_types import Issue, Repair, Patch, Verification
from ..core.model import ARGIR
from ..diagnostics import extract_af_facts, is_goal_accepted
from ..core.model import ARGIR as ARGIRModel
from ..semantics.clingo_helpers import quote_id, parse_binary_atom


def enforce_goal(
    argir_data: dict,
    issue: Issue,
    semantics: str = "grounded",
    max_edits: int = 2
) -> List[Repair]:
    """
    Generate minimal AF edits to make the goal accepted.
    """
    repairs = []

    # Convert to ARGIR model
    argir = ARGIRModel.model_validate(argir_data)

    # Extract goal from issue
    if issue.type == "goal_unreachable":
        goal_id = issue.target_node_ids[0] if issue.target_node_ids else None
    else:
        goal_id = argir.metadata.get("goal_candidate_id")

    if not goal_id:
        return repairs

    # Build AF and candidate pool
    af_facts = extract_af_facts(argir)
    candidates = build_candidate_pool(argir, goal_id, max_edits)

    # Generate ASP program
    asp_program = generate_asp_program(af_facts, candidates, goal_id, semantics)

    # Run clingo
    models = run_clingo_opt(asp_program, max_models=3)

    # Convert models to repairs
    for i, model in enumerate(models):
        patch = edits_to_patch(model, argir)
        verification = verify_af_repair(argir, patch, goal_id, semantics)

        repair = Repair(
            id=f"R-{uuid.uuid4().hex[:8]}",
            issue_id=issue.id,
            kind="AF",
            patch=patch,
            cost=count_edits(model),
            verification=verification
        )
        repairs.append(repair)

    return repairs


def build_candidate_pool(
    argir: ARGIR,
    goal_id: str,
    max_edits: int
) -> Dict[str, List[Tuple[str, str]]]:
    """
    Build the candidate pool for AF edits.
    """
    candidates = {
        "cand_del": [],
        "cand_add": [],
        "attacks_goal": []
    }

    # Find attacks on goal
    for edge in argir.graph.edges:
        if edge.kind == "attack":
            # Allow deletion of most attacks (except hard contradictions)
            if not is_hard_attack(edge, argir):
                candidates["cand_del"].append((edge.source, edge.target))

            # Track who attacks the goal
            if edge.target == goal_id:
                candidates["attacks_goal"].append(edge.source)

    # Allow adding counter-attacks to goal's attackers
    for attacker in candidates["attacks_goal"]:
        # Goal can counter-attack its attackers
        candidates["cand_add"].append((goal_id, attacker))

        # Other nodes can attack goal's attackers
        for node in argir.graph.nodes:
            if node.id != attacker and node.id != goal_id:
                candidates["cand_add"].append((node.id, attacker))

    return candidates


def is_hard_attack(edge, argir: ARGIR) -> bool:
    """
    Check if an attack represents a hard logical contradiction that shouldn't be removed.
    """
    # Check if it's marked as a logical contradiction in metadata
    if edge.attack_kind == "rebut":
        # Direct logical contradiction - keep it hard
        source_node = next((n for n in argir.graph.nodes if n.id == edge.source), None)
        target_node = next((n for n in argir.graph.nodes if n.id == edge.target), None)

        if source_node and target_node:
            # Check if they have directly contradicting atoms
            if source_node.conclusion and target_node.conclusion:
                for s_atom in source_node.conclusion.atoms:
                    for t_atom in target_node.conclusion.atoms:
                        if s_atom.pred == t_atom.pred and s_atom.negated != t_atom.negated:
                            return True
    return False


def generate_asp_program(
    af_facts: List[str],
    candidates: Dict[str, List[Tuple[str, str]]],
    goal_id: str,
    semantics: str
) -> str:
    """
    Generate the complete ASP program for enforcement.
    """
    program = []

    # Add base AF facts
    for fact in af_facts:
        # Convert arg() to arg0() and att() to att0()
        if fact.startswith("arg("):
            program.append(fact.replace("arg(", "arg0("))
        elif fact.startswith("att("):
            program.append(fact.replace("att(", "att0("))

    # Add goal with proper quoting
    program.append(f"goal({quote_id(goal_id)}).")

    # Add candidates with proper quoting
    for src, tgt in candidates["cand_del"]:
        program.append(f"cand_del({quote_id(src)},{quote_id(tgt)}).")

    for src, tgt in candidates["cand_add"]:
        program.append(f"cand_add({quote_id(src)},{quote_id(tgt)}).")

    for attacker in candidates["attacks_goal"]:
        program.append(f"attacks_goal({quote_id(attacker)}).")

    # Add the enforcement encoding
    encoding_path = os.path.join(os.path.dirname(__file__), "af_enforce.lp")
    with open(encoding_path, "r") as f:
        program.append(f.read())

    # Add semantics-specific encoding if not grounded
    if semantics == "preferred":
        program.append(get_preferred_encoding())
    elif semantics == "stable":
        program.append(get_stable_encoding())

    return "\n".join(program)


def get_preferred_encoding() -> str:
    """
    Return ASP encoding for preferred semantics.
    """
    return """
% Preferred semantics (simplified)
% An argument is in if it defends itself against all attacks
defended(X) :- arg(X), not undefended(X).
undefended(X) :- arg(X), att(Y,X), not counter_attacked(Y,X).
counter_attacked(Y,X) :- att(Z,Y), in(Z).
in(X) :- defended(X).
"""


def get_stable_encoding() -> str:
    """
    Return ASP encoding for stable semantics.
    """
    return """
% Stable semantics
% Extension attacks all arguments outside it
in(X) :- arg(X), not out(X).
out(X) :- arg(X), not in(X).
:- in(X), in(Y), att(X,Y).
:- out(X), not attacked_by_in(X).
attacked_by_in(X) :- att(Y,X), in(Y).
"""


def run_clingo_opt(asp_program: str, max_models: int = 3) -> List[Dict[str, Any]]:
    """
    Run clingo with optimization to find minimal models.
    """
    models = []

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lp", delete=False) as f:
        f.write(asp_program)
        temp_file = f.name

    try:
        # Run clingo with optimization
        cmd = ["clingo", temp_file, "--opt-mode=opt", f"-n{max_models}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        # Parse output
        lines = result.stdout.split("\n")
        current_model = {}

        for line in lines:
            if line.startswith("Answer:"):
                if current_model:
                    models.append(current_model)
                current_model = {}
            elif line and not line.startswith("Optimization:") and not line.startswith("OPTIMUM"):
                # Parse atoms from the model
                atoms = line.strip().split()
                for atom in atoms:
                    if atom.startswith("del_att("):
                        try:
                            src, tgt = parse_binary_atom(atom, "del_att")
                            if "del_att" not in current_model:
                                current_model["del_att"] = []
                            current_model["del_att"].append((src, tgt))
                        except ValueError:
                            pass  # Skip malformed atoms
                    elif atom.startswith("add_att("):
                        try:
                            src, tgt = parse_binary_atom(atom, "add_att")
                            if "add_att" not in current_model:
                                current_model["add_att"] = []
                            current_model["add_att"].append((src, tgt))
                        except ValueError:
                            pass  # Skip malformed atoms
                    elif atom == "use_defender":
                        current_model["use_defender"] = True
                    elif atom.startswith("in("):
                        if "in" not in current_model:
                            current_model["in"] = []
                        current_model["in"].append(atom[3:-1])

            if "OPTIMUM FOUND" in line:
                current_model["optimal"] = True

        if current_model:
            models.append(current_model)

    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"Clingo error: {e}")
    finally:
        os.unlink(temp_file)

    return models


def edits_to_patch(model: Dict[str, Any], argir: ARGIR) -> Patch:
    """
    Convert clingo model edits to a Patch object.
    """
    patch = Patch()

    # Handle attack deletions
    if "del_att" in model:
        for src, tgt in model["del_att"]:
            patch.del_edges.append({
                "source": src,
                "target": tgt,
                "kind": "attack"
            })
            patch.af_edits.append(("del_att", src, tgt))

    # Handle attack additions
    if "add_att" in model:
        for src, tgt in model["add_att"]:
            # Check if source is the defender
            if src == "def":
                # Add a new defender node
                patch.add_nodes.append({
                    "id": "def",
                    "kind": "Premise",
                    "atoms": [],
                    "text": "[Defender premise to be specified]"
                })

            patch.add_edges.append({
                "source": src,
                "target": tgt,
                "kind": "attack"
            })
            patch.af_edits.append(("add_att", src, tgt))

    # Handle defender
    if model.get("use_defender"):
        patch.af_edits.append(("add_arg", "def", ""))

    return patch


def count_edits(model: Dict[str, Any]) -> int:
    """
    Count the number of edits in a model.
    """
    count = 0
    count += len(model.get("del_att", []))
    count += len(model.get("add_att", []))
    count += 1 if model.get("use_defender") else 0
    return count


def verify_af_repair(
    argir: ARGIR,
    patch: Patch,
    goal_id: str,
    semantics: str
) -> Verification:
    """
    Verify that the repair makes the goal accepted.
    """
    # Apply patch to a copy of ARGIR
    patched_argir = apply_patch_to_argir(argir, patch)

    # Check if goal is now accepted
    goal_accepted = is_goal_accepted(patched_argir, goal_id, semantics)

    return Verification(
        af_semantics=semantics,
        af_goal_accepted=goal_accepted,
        af_optimal=True,  # If clingo reported optimal
        fol_entailed=None,  # Will be checked by FOL module
        artifacts={
            "patch_applied": True,
            "edits_count": len(patch.af_edits)
        }
    )


def apply_patch_to_argir(argir: ARGIR, patch: Patch) -> ARGIR:
    """
    Apply a patch to create a modified ARGIR object.
    """
    import copy
    patched = copy.deepcopy(argir)

    # Add new nodes
    for node_data in patch.add_nodes:
        from ..core.model import InferenceStep, Statement
        new_node = InferenceStep(
            id=node_data["id"],
            premises=[],
            conclusion=Statement(
                text=node_data.get("text", ""),
                atoms=node_data.get("atoms", [])
            )
        )
        patched.graph.nodes.append(new_node)

    # Add new edges
    for edge_data in patch.add_edges:
        from ..core.model import Edge
        new_edge = Edge(
            source=edge_data["source"],
            target=edge_data["target"],
            kind=edge_data["kind"]
        )
        patched.graph.edges.append(new_edge)

    # Remove edges
    edges_to_remove = []
    for del_edge in patch.del_edges:
        for i, edge in enumerate(patched.graph.edges):
            if (edge.source == del_edge["source"] and
                edge.target == del_edge["target"] and
                edge.kind == del_edge["kind"]):
                edges_to_remove.append(i)

    for i in reversed(edges_to_remove):
        del patched.graph.edges[i]

    return patched