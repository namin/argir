#!/usr/bin/env python3
import argparse, json, os, re, sys, time, zipfile
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from pathlib import Path
import os

HOST = os.getenv("HOST", "https://argir.metareflective.app")
BASE = f"{HOST}/plain"

def fetch(url, binary=False):
    print(f"Fetching {url}")
    req = Request(url, headers={"User-Agent":"argir-offline-export/1.0"})
    with urlopen(req, timeout=30) as r:
        data = r.read()
        return data if binary else data.decode("utf-8", errors="replace")

def write(path, content, binary=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if binary else "w"
    with open(path, mode) as f:
        f.write(content)

def undirected_components(nodes, edges):
    nbr = {n["id"]: set() for n in nodes}
    for e in edges:
        a, b = e.get("source"), e.get("target")
        if a in nbr and b in nbr:
            nbr[a].add(b); nbr[b].add(a)
    seen, comps = set(), []
    for nid in nbr:
        if nid in seen: continue
        stack, comp = [nid], set()
        while stack:
            x = stack.pop()
            if x in comp: continue
            comp.add(x); seen.add(x)
            stack.extend(nbr[x])
        comps.append(comp)
    return comps

def support_outdeg(nodes, edges):
    outs = {n["id"]:0 for n in nodes}
    for e in edges:
        if e.get("kind") == "support":
            src = e.get("source"); 
            if src in outs: outs[src] += 1
    return outs

def goal_as_axiom(fof_text):
    goal = None
    axiom_forms = []
    for line in fof_text.splitlines():
        s = line.strip()
        if s.startswith("fof(goal"):
            m = re.search(r"fof\(goal\s*,\s*conjecture\s*,(.*)\)\s*\.\s*$", s)
            if m: goal = re.sub(r"\s+", "", m.group(1))
        elif s.startswith("fof(") and ", axiom," in s:
            m = re.search(r"fof\([^,]+,\s*axiom\s*,(.*)\)\s*\.\s*$", s)
            if m: axiom_forms.append(re.sub(r"\s+", "", m.group(1)))
    return goal is not None and goal in axiom_forms

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="argir-export", help="output folder")
    ap.add_argument("--hash", action="append", help="hash(es) to fetch")
    ap.add_argument("--hashes-file", help="file with one hash per line")
    ap.add_argument("--zip", dest="zipname", help="also write a ZIP file")
    args = ap.parse_args()

    hashes = set(args.hash or [])
    if args.hashes_file:
        with open(args.hashes_file) as f:
            for line in f:
                line=line.strip()
                if line: hashes.add(line)
    if not hashes:
        print("No hashes provided, using saved/*.json")
        hashes = [h.stem for h in Path("saved").glob("*.json")]
    if not hashes:
        print("Provide --hash or --hashes-file", file=sys.stderr); sys.exit(2)

    out = Path(args.out)
    manifest = {
        "version": 1,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source_host": HOST,
        "examples": []
    }

    for h in sorted(hashes):
        base = f"{BASE}/{h}"
        exdir = out / "examples" / h
        print(f"[*] {h}")
        # Fetch core artifacts
        saved_json = fetch(f"{base}.json")
        report_md  = fetch(f"{base}.md")
        # txt/html optional; ignore failures
        try: report_txt = fetch(f"{base}.txt")
        except: report_txt = ""
        try: report_html = fetch(f"{base}.html")
        except: report_html = ""
        saved = json.loads(saved_json)
        result = (saved.get("result") or {})
        argir  = result.get("argir") or {}
        graph  = (argir.get("graph") or {})
        nodes  = graph.get("nodes") or []
        edges  = graph.get("edges") or []
        fof_raw = result.get("fof") or []
        fof = "\n".join(fof_raw) if isinstance(fof_raw, list) else str(fof_raw)

        # Write files
        write(exdir/"saved.json", json.dumps(saved, ensure_ascii=False, indent=2))
        write(exdir/"report.md", report_md)
        if report_txt:  write(exdir/"report.txt", report_txt)
        if report_html: write(exdir/"report.html", report_html)
        write(exdir/"fof.fol", fof)
        write(exdir/"argir.json", json.dumps(argir, ensure_ascii=False, indent=2))

        # CSVs
        import csv
        with open(exdir/"nodes.csv", "w", newline="") as f:
            w=csv.writer(f); w.writerow(["id","label","kind"])
            for n in nodes: w.writerow([n.get("id",""), n.get("label",""), n.get("kind","")])
        with open(exdir/"edges.csv", "w", newline="") as f:
            w=csv.writer(f); w.writerow(["source","target","kind"])
            for e in edges: w.writerow([e.get("source",""), e.get("target",""), e.get("kind","")])

        # Summary
        comps = undirected_components(nodes, edges)
        outdeg = support_outdeg(nodes, edges)
        meta = (argir.get("metadata") or {})
        goal_id = meta.get("goal_id", "")
        # Reachability over support edges
        inc = {n["id"]: set() for n in nodes}
        outs= {n["id"]: set() for n in nodes}
        for e in edges:
            if e.get("kind")=="support":
                outs[e["source"]].add(e["target"])
                inc[e["target"]].add(e["source"])
                inc.setdefault(e["source"], set())
        roots = [nid for nid in inc if len(inc[nid])==0]
        seen=set(); stack=list(roots)
        while stack:
            x=stack.pop()
            if x in seen: continue
            seen.add(x)
            stack.extend(list(outs.get(x,())))
        # Sinks in goal component
        gc = None
        if goal_id:
            for c in comps:
                if goal_id in c: gc = c; break
        if gc is None: gc = comps[0] if comps else set()
        num_sinks = sum(1 for nid,deg in outdeg.items() if nid in gc and deg==0)
        summary = {
            "hash": h,
            "created_at": (saved.get("saved") or {}).get("createdAt",""),
            "goal_id": goal_id,
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "num_components": len(comps),
            "num_support_sinks": num_sinks,
            "goal_reachable_from_premises": (goal_id in seen) if goal_id else None,
            "eprover": {
                "status": "Theorem" if (result.get("fol_summary") or {}).get("theorem") else
                          ("Unsat" if (result.get("fol_summary") or {}).get("unsat") else
                           ("Sat" if (result.get("fol_summary") or {}).get("sat") else "Unknown")),
                "note": (result.get("fol_summary") or {}).get("note","")
            },
            "has_goal_as_axiom": goal_as_axiom(fof)
        }
        write(exdir/"summary.json", json.dumps(summary, ensure_ascii=False, indent=2))

        manifest["examples"].append({
            "hash": h,
            "title": (saved.get("title") or ""),
            "plain_base": base,
            "paths": {
                "saved": str(exdir/"saved.json"),
                "report_md": str(exdir/"report.md"),
                "fof": str(exdir/"fof.fol"),
                "argir": str(exdir/"argir.json"),
                "nodes_csv": str(exdir/"nodes.csv"),
                "edges_csv": str(exdir/"edges.csv"),
                "summary": str(exdir/"summary.json")
            }
        })

    (Path(args.out)).mkdir(parents=True, exist_ok=True)
    with open(Path(args.out)/"manifest.json","w") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if args.zipname:
        zpath = Path(args.zipname)
        with zipfile.ZipFile(zpath, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for p in Path(args.out).rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(args.out))
        print(f"[+] Wrote {zpath}")

if __name__ == "__main__":
    main()
