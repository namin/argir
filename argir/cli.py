from __future__ import annotations
import argparse, os, json, sys
import argir as _argir_pkg
from .pipeline import run_pipeline

def main():
    parser = argparse.ArgumentParser(description=f"ARGIR pipeline (v{_argir_pkg.__version__})")
    parser.add_argument("input", help="Path to text file")
    parser.add_argument("--out", default="out", help="Output folder")
    parser.add_argument("--defeasible-fol", action="store_true", help="Export FOL with simple defeasible exceptions (~exceptions in antecedent)")
    parser.add_argument("--goal", help="Node id to use as the conjecture goal (overrides auto selection)")
    parser.add_argument("--strict", action="store_true", help="Enable strict validation checks (shows warnings for incomplete reasoning)")
    parser.add_argument("--strict-fail", action="store_true", help="Fail on strict validation errors (for CI/CD)")
    parser.add_argument("-V","--version", action="store_true", help="Print version and module path and exit")
    args = parser.parse_args()

    if args.version:
        print(f"ARGIR v{_argir_pkg.__version__} @ {_argir_pkg.__file__}")
        return

    with open(args.input, "r", encoding="utf-8") as f:
        text = f.read()
    print(f"[ARGIR] Using package at: {_argir_pkg.__file__} (v{_argir_pkg.__version__})")

    # Enable strict by default or if explicitly requested
    strict = args.strict or args.strict_fail or True  # Default to True
    res = run_pipeline(text, fol_mode=("defeasible" if args.defeasible_fol else "classical"), goal_id=args.goal, strict=strict)

    # Handle validation issues
    if res.get('validation_issues'):
        print("\n⚠️  Validation issues detected:")
        for issue in res['validation_issues']:
            print(f"  • Node '{issue['node']}': {issue['message']}")
        print("\nThese warnings indicate potentially incomplete reasoning.")

        if args.strict_fail:
            print("\nExiting with error due to --strict-fail flag.")
            sys.exit(1)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "argir.json"), "w", encoding="utf-8") as f: json.dump(res["argir"], f, indent=2)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f: f.write(res["report_md"])
    with open(os.path.join(args.out, "fof.p"), "w", encoding="utf-8") as f: f.write("\n".join(res["fof"])+"\n")
    with open(os.path.join(args.out, "draft.json"), "w", encoding="utf-8") as f: json.dump(res.get("draft", {}), f, indent=2)
    with open(os.path.join(args.out, "fol_summary.json"), "w", encoding="utf-8") as f: json.dump(res.get("fol_summary", {}), f, indent=2)
    print("Wrote:", args.out)

if __name__ == "__main__":
    main()
