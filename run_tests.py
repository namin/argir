
#!/usr/bin/env python3
import os, sys, subprocess, argparse

def main():
    ap = argparse.ArgumentParser(description="Run ARGIR test suite")
    ap.add_argument("--fixtures", action="store_true", help="Run with golden fixtures (no LLM calls)")
    ap.add_argument("--llm", action="store_true", help="Force LLM mode (ignore fixtures)")
    ap.add_argument("--fol", choices=["classical","defeasible"], default=None, help="Force fol mode for all tests that don't override")
    ap.add_argument("--python", default=sys.executable, help="Python interpreter to use")
    args = ap.parse_args()

    env = os.environ.copy()
    if args.fixtures and not args.llm:
        env["ARGIR_TEST_MODE"] = "fixtures"
    elif args.llm:
        env.pop("ARGIR_TEST_MODE", None)

    # Optionally force fol mode by wrapping unittest discovery (not per-test granularity)
    cmd = [args.python, "-m", "unittest", "discover", "-s", "tests", "-p", "test_suite.py", "-v"]
    print(">> Running:", " ".join(cmd))
    rc = subprocess.call(cmd, env=env)
    sys.exit(rc)

if __name__ == "__main__":
    main()
