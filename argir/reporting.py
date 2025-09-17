from __future__ import annotations
from typing import List, Dict, Any, Optional
import json
import hashlib
from .repair_types import Issue, Repair


def run_hash(argir_obj: dict, settings: dict) -> str:
    """Generate a stable hash of the run for reproducibility tracking."""
    blob = json.dumps({"argir": argir_obj, "settings": settings}, sort_keys=True).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:12]


def render_diagnosis_report(
    issues: List[Issue],
    repairs: List[Repair],
    existing_report: str = "",
    run_info: Optional[dict] = None
) -> str:
    """
    Generate a markdown report with issue cards and repairs.
    """
    if not existing_report:
        report = ["# ARGIR Analysis Report\n"]
    else:
        report = [existing_report]

    # Add run info if provided
    if run_info:
        report.append(f"\n**Run:** {run_info.get('hash', 'unknown')} | ")
        report.append(f"semantics={run_info.get('semantics', 'grounded')} | ")
        report.append(f"max_abduce={run_info.get('max_abduce', 2)} | ")
        report.append(f"timeout={run_info.get('timeout', 2.0)}s\n")

    # Add diagnosis section
    report.append("\n## Issues & Repairs\n")

    if not issues:
        report.append("✅ No issues detected in the argument structure.\n")
        return "\n".join(report)

    report.append(f"Found {len(issues)} issue(s) in the argument structure:\n")

    # Group repairs by issue
    repairs_by_issue = {}
    for repair in repairs:
        if repair.issue_id not in repairs_by_issue:
            repairs_by_issue[repair.issue_id] = []
        repairs_by_issue[repair.issue_id].append(repair)

    # Render each issue with its repairs
    for issue in issues:
        report.append(render_issue_card(issue, repairs_by_issue.get(issue.id, [])))

    return "\n".join(report)


def render_issue_card(issue: Issue, repairs: List[Repair]) -> str:
    """
    Render a single issue as a formatted card.
    """
    card = []

    # Issue header
    issue_type_display = {
        "unsupported_inference": "Unsupported Inference",
        "circular_support": "Circular Support",
        "contradiction_unresolved": "Unresolved Contradiction",
        "weak_scheme_instantiation": "Weak Scheme Instantiation",
        "goal_unreachable": "Goal Unreachable"
    }

    card.append(f"\n### Issue {issue.id}: {issue_type_display.get(issue.type, issue.type)}")

    # Target nodes
    if issue.target_node_ids:
        targets = ", ".join(issue.target_node_ids)
        card.append(f"**Affected nodes:** {targets}")

    # Issue description
    card.append(f"\n**Why:** {get_issue_description(issue)}")

    # Evidence
    if issue.evidence:
        card.append("\n**Evidence:**")
        card.append(format_evidence(issue.evidence))

    # Repairs
    if repairs:
        # Sort repairs by cost
        repairs = sorted(repairs, key=lambda r: r.cost)

        # Show primary repair
        primary = repairs[0]
        card.append("\n**Minimal repair (verified):**")
        card.append(format_repair(primary))

        # Show alternatives if any
        if len(repairs) > 1:
            card.append("\n**Alternative repairs:**")
            for alt in repairs[1:3]:  # Show up to 2 alternatives
                card.append(format_repair_summary(alt))
    else:
        card.append("\n**Status:** No automated repair available")

    return "\n".join(card)


def get_issue_description(issue: Issue) -> str:
    """
    Generate a human-readable description of the issue.
    """
    descriptions = {
        "unsupported_inference": "Premises do not entail the conclusion; the inference lacks logical support.",
        "circular_support": "The argument depends on itself through a circular chain of reasoning.",
        "contradiction_unresolved": "Conflicting conclusions are both accepted, creating an inconsistency.",
        "weak_scheme_instantiation": "The argumentation scheme is missing critical backing or evidence.",
        "goal_unreachable": "The goal cannot be accepted under the current argumentation framework."
    }

    base_desc = descriptions.get(issue.type, "Issue detected in argument structure.")

    # Add specific details from evidence
    if issue.type == "circular_support" and "cycle_path" in issue.evidence:
        base_desc += f" Cycle: {issue.evidence['cycle_path']}"
    elif issue.type == "unsupported_inference":
        if issue.evidence.get("af_rejected"):
            base_desc += " Node is also rejected in the AF."

    return base_desc


def format_evidence(evidence: Dict[str, Any]) -> str:
    """
    Format evidence dictionary into readable markdown.
    """
    lines = []

    if "cycle_path" in evidence:
        lines.append(f"- Cycle detected: `{evidence['cycle_path']}`")

    if "conflicting_atoms" in evidence:
        for conflict in evidence["conflicting_atoms"]:
            lines.append(f"- Node `{conflict['node']}`: {format_atom(conflict['atom'])}")

    if "missing_critical_questions" in evidence:
        lines.append("- Missing critical questions:")
        for cq in evidence["missing_critical_questions"]:
            lines.append(f"  - {cq}")

    if "premises" in evidence and len(evidence["premises"]) > 0:
        lines.append(f"- Premise count: {len(evidence['premises'])}")

    if "fol_check_failed" in evidence and evidence["fol_check_failed"]:
        lines.append("- FOL entailment check: ❌ Failed")

    if "af_rejected" in evidence and evidence["af_rejected"]:
        lines.append("- AF acceptance: ❌ Rejected")

    return "\n".join(lines) if lines else "- No detailed evidence available"


def format_atom(atom: Dict[str, Any]) -> str:
    """
    Format an atom dictionary into readable string.
    """
    pred = atom.get("pred", "?")
    args = atom.get("args", [])
    negated = atom.get("negated", False)

    if args:
        args_str = ",".join(arg.get("name", "?") for arg in args)
        atom_str = f"{pred}({args_str})"
    else:
        atom_str = pred

    return f"¬{atom_str}" if negated else atom_str


def format_repair(repair: Repair) -> str:
    """
    Format a repair with full details.
    """
    lines = []

    # Repair actions
    if repair.patch.add_nodes:
        for node in repair.patch.add_nodes:
            lines.append(f"- Add premise: {node.get('text', node.get('id'))}")

    if repair.patch.add_edges:
        for edge in repair.patch.add_edges:
            lines.append(f"- Add {edge['kind']}: {edge['source']} → {edge['target']}")

    if repair.patch.del_edges:
        for edge in repair.patch.del_edges:
            lines.append(f"- Remove {edge['kind']}: {edge['source']} → {edge['target']}")

    if repair.patch.fol_hypotheses:
        lines.append(f"- FOL hypothesis: {', '.join(repair.patch.fol_hypotheses)}")

    # Verification
    lines.append("\n**Verification:**")
    verif = repair.verification

    # FOL verification
    if verif.fol_entailed is not None:
        if verif.fol_entailed:
            lines.append("- FOL (E-prover): entailed ✅")
        else:
            lines.append("- FOL (E-prover): not entailed ❌")

    # AF verification - use rich data if available
    af_impact = verif.artifacts.get("af_impact") if verif.artifacts else None

    if af_impact:
        # Rich AF impact information
        target = af_impact.get("target", {})
        goal = af_impact.get("goal", {})

        if target.get("id"):
            if target.get("changed"):
                status = "accepted" if target.get("after") else "rejected"
                lines.append(f"- AF ({verif.af_semantics}): node {target['id']} becomes {status} ✅")
            else:
                status = "accepted" if target.get("after") else "not accepted"
                lines.append(f"- AF ({verif.af_semantics}): node {target['id']} remains {status} ℹ️")

        if goal and goal.get("id") and goal["id"] != target.get("id"):
            if goal.get("changed"):
                status = "accepted" if goal.get("after") else "rejected"
                lines.append(f"- AF ({verif.af_semantics}): goal {goal['id']} becomes {status} ✅")
            else:
                status = "accepted" if goal.get("after") else "not accepted"
                lines.append(f"- AF ({verif.af_semantics}): goal {goal['id']} remains {status} ℹ️")

        if af_impact.get("explanation"):
            lines.append(f"  Note: {af_impact['explanation']}")
    else:
        # Fallback to legacy format
        if verif.af_goal_accepted:
            lines.append(f"- AF ({verif.af_semantics}): goal accepted ✅")
        else:
            lines.append(f"- AF ({verif.af_semantics}): goal not accepted ❌")

    if verif.af_optimal:
        lines.append(f"- Optimality: minimal (cost={repair.cost})")

    # Machine-readable patch
    lines.append("\n**Patch (machine-readable):**")
    lines.append("```json")
    lines.append(json.dumps(repair.patch.model_dump(), indent=2))
    lines.append("```")

    return "\n".join(lines)


def format_repair_summary(repair: Repair) -> str:
    """
    Format a brief summary of an alternative repair.
    """
    summary = f"- Cost {repair.cost}: "

    actions = []
    if repair.patch.add_nodes:
        actions.append(f"add {len(repair.patch.add_nodes)} node(s)")
    if repair.patch.add_edges:
        actions.append(f"add {len(repair.patch.add_edges)} edge(s)")
    if repair.patch.del_edges:
        actions.append(f"remove {len(repair.patch.del_edges)} edge(s)")

    summary += ", ".join(actions) if actions else "no changes"

    if repair.verification.af_goal_accepted:
        summary += " (verified ✅)"
    else:
        summary += " (not verified ❌)"

    return summary


def save_repairs_json(
    issues: List[Issue],
    repairs: List[Repair],
    output_path: str
):
    """
    Save issues and repairs to a JSON file.
    """
    data = {
        "issues": [issue.model_dump() for issue in issues],
        "repairs": [repair.model_dump() for repair in repairs]
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)