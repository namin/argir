from __future__ import annotations
import argparse, os, json, sys
from typing import Optional
import argir as _argir_pkg
from .pipeline import run_pipeline, run_pipeline_soft
from .diagnostics import diagnose
from .repairs.af_enforce import enforce_goal
from .repairs.fol_abduction import abduce_missing_premises
from .reporting import render_diagnosis_report, save_repairs_json, run_hash


def auto_detect_goal(argir_obj: dict) -> Optional[str]:
    """Automatically detect the goal node from metadata or graph structure."""
    meta = (argir_obj.get("metadata") or {})
    for k in ("goal_id", "goal_candidate_id"):
        if meta.get(k):
            return meta[k]

    nodes = argir_obj.get("graph", {}).get("nodes", [])
    edges = argir_obj.get("graph", {}).get("edges", [])
    node_by_id = {n["id"]: n for n in nodes}

    # Prefer "claim-like" nodes with the most incoming supports
    support_in = {}
    for e in edges:
        if e.get("kind") == "support":
            support_in[e["target"]] = support_in.get(e["target"], 0) + 1
    if support_in:
        goal = max(support_in.items(), key=lambda kv: kv[1])[0]
        if goal in node_by_id:
            return goal

    # Fallback: any node that is attacked (often the debated claim)
    attacked = [e["target"] for e in edges if e.get("kind") == "attack"]
    return attacked[0] if attacked else None

def main():
    parser = argparse.ArgumentParser(description=f"ARGIR pipeline (v{_argir_pkg.__version__})")
    parser.add_argument("input", help="Path to text file")
    parser.add_argument("--out", default="out", help="Output folder")
    parser.add_argument("--defeasible-fol", action="store_true", help="Export FOL with simple defeasible exceptions (~exceptions in antecedent)")
    parser.add_argument("--goal", help="Node id to use as the conjecture goal (overrides auto selection)")
    parser.add_argument("--goal-hint", help="Text hint to help LLM identify the goal claim")
    parser.add_argument("--strict-fail", action="store_true", help="Fail on strict validation errors (for CI/CD)")
    parser.add_argument("--soft", action="store_true", help="Use soft IR extraction with deterministic canonicalization")
    parser.add_argument("--k-samples", type=int, default=1, help="Number of soft IR samples to try (picks best)")
    parser.add_argument("--diagnose", action="store_true", help="Detect issues in the argument structure")
    parser.add_argument("--repair", action="store_true", help="Generate and verify repairs for detected issues")
    parser.add_argument("--semantics", choices=["grounded", "preferred", "stable"], default="grounded", help="AF semantics to use (default: grounded)")
    parser.add_argument("--max-af-edits", type=int, default=2, help="Maximum AF edits for repair (default: 2)")
    parser.add_argument("--max-abduce", type=int, default=2, help="Maximum atoms for abduction (default: 2)")
    parser.add_argument("--abduce-timeout", type=float, default=2.0, help="Timeout for abduction E-prover calls in seconds (default: 2.0)")
    parser.add_argument("--repair-friendly", action="store_true", help="Use repair-friendly mode (filter empty IR nodes, split conjunctions)")
    parser.add_argument("--eprover-path", help="Path to E-prover executable (optional)")
    parser.add_argument("-V","--version", action="store_true", help="Print version and module path and exit")
    args = parser.parse_args()

    if args.version:
        print(f"ARGIR v{_argir_pkg.__version__} @ {_argir_pkg.__file__}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    print(f"[ARGIR] Using package at: {_argir_pkg.__file__} (v{_argir_pkg.__version__})")

    # Choose pipeline based on --soft flag
    if args.soft:
        print(f"[ARGIR] Using soft IR pipeline with k={args.k_samples} samples")
        res = run_pipeline_soft(text,
                              fol_mode=("defeasible" if args.defeasible_fol else "classical"),
                              goal_id=args.goal,
                              goal_hint=args.goal_hint,
                              k_samples=args.k_samples)
    else:
        res = run_pipeline(text, fol_mode=("defeasible" if args.defeasible_fol else "classical"), goal_id=args.goal)

    # Handle validation issues
    if args.soft and res.get('soft_validation'):
        # For soft pipeline, show validation report
        validation_report = res['soft_validation']
        if validation_report.errors():
            print("\n❌ Soft IR validation errors:")
            for issue in validation_report.errors():
                print(f"  • [{issue.code}] {issue.path}: {issue.message}")
        if validation_report.warn():
            print("\n⚠️  Soft IR validation warnings:")
            for issue in validation_report.warn():
                print(f"  • [{issue.code}] {issue.path}: {issue.message}")
    elif res.get('validation_issues'):
        print("\n⚠️  Validation issues detected:")
        for issue in res['validation_issues']:
            print(f"  • Node '{issue['node']}': {issue['message']}")
        print("\nThese warnings indicate potentially incomplete reasoning.")

        if args.strict_fail:
            print("\nExiting with error due to --strict-fail flag.")
            sys.exit(1)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "argir.json"), "w", encoding="utf-8") as f: json.dump(res["argir"], f, indent=2)

    # Run diagnosis if requested
    issues = []
    repairs = []
    if args.diagnose or args.repair:
        # Auto-detect goal if not provided
        goal = args.goal or auto_detect_goal(res["argir"])
        if goal and not args.goal:
            print(f"\n[ARGIR] Auto-detected goal: {goal}")
        elif not goal and args.repair:
            print("[ARGIR] No goal detected; pass --goal to enable repairs.")

        print("\n[ARGIR] Running diagnosis...")
        issues = diagnose(
            res["argir"],
            goal_id=goal,
            semantics=args.semantics,
            eprover_path=args.eprover_path
        )

        print(f"[ARGIR] Found {len(issues)} issue(s)")

        # Save issues
        with open(os.path.join(args.out, "issues.json"), "w", encoding="utf-8") as f:
            json.dump([issue.model_dump() for issue in issues], f, indent=2)

        # Generate repairs if requested
        if args.repair and issues:
            print("\n[ARGIR] Generating repairs...")
            for issue in issues:
                print(f"  • Repairing {issue.id}: {issue.type}")

                if issue.type in ["goal_unreachable", "contradiction_unresolved"]:
                    issue_repairs = enforce_goal(
                        res["argir"],
                        issue,
                        semantics=args.semantics,
                        max_edits=args.max_af_edits
                    )
                    repairs.extend(issue_repairs)

                if issue.type in ["unsupported_inference", "weak_scheme_instantiation"]:
                    issue_repairs = abduce_missing_premises(
                        res["argir"],
                        issue,
                        max_atoms=args.max_abduce,
                        timeout=args.abduce_timeout,
                        eprover_path=args.eprover_path
                    )
                    repairs.extend(issue_repairs)

            print(f"[ARGIR] Generated {len(repairs)} repair(s)")

            # Save repairs
            save_repairs_json(issues, repairs, os.path.join(args.out, "repairs.json"))

    # Update report with diagnosis
    if issues or repairs:
        # Generate run hash and info
        settings = {
            "semantics": args.semantics,
            "max_abduce": args.max_abduce,
            "timeout": args.abduce_timeout,
            "repair_friendly": args.repair_friendly
        }
        run_info = {
            "hash": run_hash(res["argir"], settings),
            "semantics": args.semantics,
            "max_abduce": args.max_abduce,
            "timeout": args.abduce_timeout
        }
        res["report_md"] = render_diagnosis_report(issues, repairs, res["report_md"], run_info)

    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f: f.write(res["report_md"])
    with open(os.path.join(args.out, "fof.p"), "w", encoding="utf-8") as f: f.write("\n".join(res["fof"])+"\n")
    with open(os.path.join(args.out, "draft.json"), "w", encoding="utf-8") as f: json.dump(res.get("draft", {}), f, indent=2)
    with open(os.path.join(args.out, "fol_summary.json"), "w", encoding="utf-8") as f: json.dump(res.get("fol_summary", {}), f, indent=2)
    print("Wrote:", args.out)

if __name__ == "__main__":
    main()
