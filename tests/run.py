#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, re, shutil, subprocess, sys, glob, zipfile

OUTPUT_FILES = ["argir.json", "fof.p", "fol_summary.json", "report.md"]

def read_cases(path: str):
    cases = []
    for fp in sorted(glob.glob(os.path.join(path, "*.json"))):
        with open(fp, "r", encoding="utf-8") as f:
            obj = json.load(f)
        cases.append(obj)
    return cases

def ensure_dir(p: str): os.makedirs(p, exist_ok=True)

def run_cli(input_path: str, out_dir: str, default_opts, case_opts):
    opts = dict(default_opts); opts.update(case_opts or {})
    cmd = [sys.executable, "-m", "argir.cli", input_path, "--out", out_dir]
    if opts.get("soft"): cmd.append("--soft")
    if "k_samples" in opts: cmd.extend(["--k-samples", str(opts["k_samples"])])
    if opts.get("defeasible_fol"): cmd.append("--defeasible-fol")
    if "goal" in opts and opts["goal"]: cmd.extend(["--goal", str(opts["goal"])])

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return proc.returncode, proc.stdout, " ".join(cmd)
    except Exception:
        cmd = ["argir", input_path, "--out", out_dir]
        if opts.get("soft"): cmd.append("--soft")
        if "k_samples" in opts: cmd.extend(["--k-samples", str(opts["k_samples"])])
        if opts.get("defeasible_fol"): cmd.append("--defeasible-fol")
        if "goal" in opts and opts["goal"]: cmd.extend(["--goal", str(opts["goal"])])
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return proc.returncode, proc.stdout, " ".join(cmd)

def read_file(p: str) -> str:
    try:
        with open(p, "r", encoding="utf-8") as f: return f.read()
    except Exception:
        return ""

def load_json(p: str):
    try:
        with open(p, "r", encoding="utf-8") as f: return json.load(f)
    except Exception:
        return {}

def parse_goal_quantifier(fof_text: str) -> str:
    import re
    m = re.search(r'fof\(\s*goal\s*,\s*conjecture\s*,\s*(.*?)\)\s*\.', fof_text, flags=re.S|re.I)
    if not m: return "none"
    body = m.group(1)
    if re.search(r'!\s*\[', body): return "forall"
    if re.search(r'\?\s*\[', body): return "exists"
    return "none"

def count_universals(fof_text: str) -> int:
    import re
    return len(re.findall(r'!\s*\[', fof_text))

def find_zero_arity_predicates(argir_json):
    preds = set()
    nodes = (argir_json.get("graph") or {}).get("nodes", [])
    for n in nodes:
        for field in ["conclusion"]:
            s = n.get(field)
            if not s: continue
            for a in (s.get("atoms") or []):
                args = a.get("args") or []
                if len(args) == 0:
                    pred = a.get("pred")
                    if pred and not pred.startswith("nl_"):
                        preds.add(pred)
        rule = n.get("rule")
        if rule:
            for part in ["antecedents","consequents"]:
                for s in (rule.get(part) or []):
                    for a in (s.get("atoms") or []):
                        args = a.get("args") or []
                        if len(args) == 0:
                            pred = a.get("pred")
                            if pred and not pred.startswith("nl_"):
                                preds.add(pred)
    return sorted(preds)

def count_attack_edges(argir_json) -> int:
    edges = (argir_json.get("graph") or {}).get("edges", [])
    return sum(1 for e in edges if e.get("kind") == "attack")

def eprover_status(fol_summary_json) -> str:
    if not fol_summary_json: return "unknown"
    if fol_summary_json.get("theorem") is True: return "theorem"
    if fol_summary_json.get("sat") is True: return "sat"
    if fol_summary_json.get("unsat") is True: return "unsat"
    return "unknown"

def run_checks(checks, fof_text, argir_json, fol_summary_json):
    import re
    ok = True; msgs = []
    if not checks: return True, msgs

    if "expect_eprover_theorem" in checks:
        status = eprover_status(fol_summary_json)
        want = checks["expect_eprover_theorem"]
        cond = (status == "theorem") if want else (status != "theorem")
        ok &= cond; msgs.append(f"eprover_theorem == {want} -> observed: {status} -> {'OK' if cond else 'FAIL'}")

    if "min_attack_edges" in checks:
        cnt = count_attack_edges(argir_json); want = int(checks["min_attack_edges"])
        cond = (cnt >= want); ok &= cond; msgs.append(f"attack_edges >= {want} -> observed: {cnt} -> {'OK' if cond else 'FAIL'}")

    if checks.get("forbid_zero_arity_non_nl"):
        zero = find_zero_arity_predicates(argir_json); cond = (len(zero) == 0)
        ok &= cond; msgs.append(f"no_zero_arity_non_nl -> observed: {zero or '[]'} -> {'OK' if cond else 'FAIL'}")

    if "goal_quantifier_in" in checks:
        gq = parse_goal_quantifier(fof_text); allowed = set(checks["goal_quantifier_in"])
        cond = (gq in allowed); ok &= cond; msgs.append(f"goal_quantifier in {sorted(allowed)} -> observed: {gq} -> {'OK' if cond else 'FAIL'}")

    for pat in checks.get("fof_must_match", []):
        m = re.search(pat, fof_text, flags=re.S); cond = m is not None
        ok &= cond; msgs.append(f"fof matches /{pat}/ -> {'OK' if cond else 'FAIL'}")

    for pat in checks.get("fof_must_not_match", []):
        m = re.search(pat, fof_text, flags=re.S); cond = m is None
        ok &= cond; msgs.append(f"fof NOT matches /{pat}/ -> {'OK' if cond else 'FAIL'}")

    return ok, msgs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-dir", default="tests/cases")
    ap.add_argument("--out-root", default="tests/out")
    ap.add_argument("--only", default="")
    ap.add_argument("--soft", action="store_true")
    ap.add_argument("--k-samples", type=int, default=1)
    ap.add_argument("--defeasible-fol", action="store_true")
    ap.add_argument("--assert", dest="assert_mode", action="store_true")
    ap.add_argument("--zip-dump", action="store_true")
    args = ap.parse_args()

    only_ids = set([s.strip() for s in args.only.split(",") if s.strip()]) if args.only else None

    default_opts = {"soft": args.soft, "k_samples": args.k_samples, "defeasible_fol": args.defeasible_fol}
    cases = read_cases(args.cases_dir)
    if only_ids: cases = [c for c in cases if c["id"] in only_ids]

    os.makedirs(args.out_root, exist_ok=True)
    summary = []
    any_fail = False

    for c in cases:
        out_dir = os.path.join(args.out_root, f"{c['id']}_{re.sub(r'\\W+','_',c['name'].lower()).strip('_')}")
        os.makedirs(out_dir, exist_ok=True)

        inp_path = os.path.join(out_dir, "input.txt")
        with open(inp_path, "w", encoding="utf-8") as f: f.write(c["text"])

        rc, stdout, cmdline = run_cli(inp_path, out_dir, default_opts, c.get("options", {}))
        with open(os.path.join(out_dir, "stdout.txt"), "w", encoding="utf-8") as f: f.write(stdout)

        fof_text = read_file(os.path.join(out_dir, "fof.p"))
        argir_json = load_json(os.path.join(out_dir, "argir.json"))
        fol_summary = load_json(os.path.join(out_dir, "fol_summary.json"))

        results = {
            "id": c["id"],
            "name": c["name"],
            "cmd": cmdline,
            "returncode": rc,
            "eprover_status": eprover_status(fol_summary),
            "goal_quantifier": parse_goal_quantifier(fof_text),
            "universals_in_fof": count_universals(fof_text),
            "zero_arity_non_nl": find_zero_arity_predicates(argir_json),
            "attack_edges": count_attack_edges(argir_json),
            "fof_size_bytes": len(fof_text.encode("utf-8")) if fof_text else 0,
        }

        ok, msgs = run_checks(c.get("checks", {}), fof_text, argir_json, fol_summary) if args.assert_mode else (True, [])
        results["checks_ok"] = ok; results["check_messages"] = msgs

        with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as f: json.dump(results, f, indent=2)
        summary.append(results)

        if not ok:
            any_fail = True
            print(f"[FAIL] {c['id']} {c['name']}")
            for m in msgs: print("   -", m)
        else:
            print(f"[ OK ] {c['id']} {c['name']}  |  eprover={results['eprover_status']}  universals={results['universals_in_fof']}  attacks={results['attack_edges']}  goalQ={results['goal_quantifier']}")

    with open("summary.json", "w", encoding="utf-8") as f: json.dump(summary, f, indent=2)

    if args.zip_dump:
        zip_name = "argir_test_dump.zip"
        with zipfile.ZipFile(zip_name, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for base, dirs, files in os.walk(args.out_root):
                for fn in files:
                    p = os.path.join(base, fn)
                    zpath = os.path.relpath(p, ".")
                    zf.write(p, zpath)
        print(f"Wrote {zip_name}")

    if args.assert_mode and any_fail:
        sys.exit(1)

if __name__ == "__main__":
    main()
