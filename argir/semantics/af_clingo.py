#!/usr/bin/env python3
# af_clingo.py — clingo-backed semantics for Dung AFs (with CLI)
from __future__ import annotations
import argparse
import json
import re
from typing import Iterable, List, Set, Tuple, FrozenSet
import clingo

# ---------- APX reading (arg/att facts) ----------
_APX_ARG = re.compile(r"\barg\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\.", re.I)
_APX_ATT = re.compile(r"\batt\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*\.", re.I)
_APX_COMM = re.compile(r"%.*?$", re.M)

def read_apx(path: str) -> Tuple[List[str], Set[Tuple[str,str]]]:
    """Read APX file and return (arguments, attacks)."""
    text = open(path, "r", encoding="utf-8").read()
    text_nc = re.sub(_APX_COMM, "", text)
    args = list(dict.fromkeys(_APX_ARG.findall(text_nc)))   # preserve order
    atts = set(_APX_ATT.findall(text_nc))
    # Ensure atoms in attacks appear as arguments
    aset = set(args)
    for u, v in atts:
        if u not in aset:
            args.append(u); aset.add(u)
        if v not in aset:
            args.append(v); aset.add(v)
    return args, atts

def facts_from_af(arguments: Iterable[str], attacks: Iterable[Tuple[str,str]]) -> str:
    parts = []
    for a in arguments: parts.append(f"arg({a}).")
    for u, v in attacks: parts.append(f"att({u},{v}).")
    return "\n".join(parts) + "\n"

# ---------- Encodings (clingo) ----------
LP_STABLE = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).                    % conflict-free
attacked(Y) :- in(X), att(X,Y).
:- arg(Y), not in(Y), not attacked(Y).        % every outsider attacked
#show in/1.
"""

LP_COMPLETE = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).                    % conflict-free
attack_in(Y) :- in(X), att(X,Y).
not_defended(X) :- att(Y,X), not attack_in(Y).
defended(X) :- arg(X), not not_defended(X).
in(X) :- defended(X).                         % include every defended
:- in(X), not defended(X).                    % exclude undefended
#show in/1.
"""

LP_GROUNDED = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).
attack_in(Y) :- in(X), att(X,Y).
not_defended(X) :- att(Y,X), not attack_in(Y).
defended(X) :- arg(X), not not_defended(X).
in(X) :- defended(X).
:- in(X), not defended(X).
#minimize { 1,X : in(X) }.                    % choose least complete = grounded
#show in/1.
"""

LP_ADMISSIBLE = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).                    % conflict-free
attack_in(Y) :- in(X), att(X,Y).
:- in(A), att(B,A), not attack_in(B).         % all members defended
#show in/1.
"""

LP_STAGE = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).
rng(Y) :- in(Y).
rng(Y) :- in(X), att(X,Y).
#maximize { 1,Y : rng(Y) }.
#show in/1.
"""

LP_SEMISTABLE = r"""
{ in(X) : arg(X) }.
:- in(X), in(Y), att(X,Y).
attack_in(Y) :- in(X), att(X,Y).
not_defended(X) :- att(Y,X), not attack_in(Y).
defended(X) :- arg(X), not not_defended(X).
in(X) :- defended(X).
:- in(X), not defended(X).                    % complete
rng(Y) :- in(Y).
rng(Y) :- in(X), att(X,Y).
#maximize { 1,Y : rng(Y) }.                   % complete with max range
#show in/1.
"""

ENCODING = {
    "stable":      LP_STABLE,
    "complete":    LP_COMPLETE,
    "grounded":    LP_GROUNDED,
    "admissible":  LP_ADMISSIBLE,  # helper for preferred
    "stage":       LP_STAGE,
    "semi-stable": LP_SEMISTABLE,
    "semistable":  LP_SEMISTABLE,
}

def _solve_models(facts: str, lp: str) -> List[FrozenSet[str]]:
    ctl = clingo.Control(["0"])  # enumerate all (optimal) models
    ctl.configuration.solve.opt_mode = "optN"
    ctl.add("base", [], facts + "\n" + lp)
    ctl.ground([("base", [])])
    out: List[FrozenSet[str]] = []
    with ctl.solve(yield_=True) as h:
        for m in h:
            # Strip quotes from node IDs that were quoted for ASP
            ext = frozenset(
                str(sym.arguments[0]).strip('"')
                for sym in m.symbols(shown=True)
                if sym.name == "in"
            )
            out.append(ext)
    return out

# ---------- Public API ----------
def grounded(arguments: Iterable[str], attacks: Iterable[Tuple[str,str]]) -> FrozenSet[str]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["grounded"])[0] if arguments else frozenset()

def complete(arguments, attacks) -> List[FrozenSet[str]]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["complete"])

def stable(arguments, attacks) -> List[FrozenSet[str]]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["stable"])

def stage(arguments, attacks) -> List[FrozenSet[str]]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["stage"])

def semi_stable(arguments, attacks) -> List[FrozenSet[str]]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["semi-stable"])

def admissible(arguments, attacks) -> List[FrozenSet[str]]:
    return _solve_models(facts_from_af(arguments, attacks), ENCODING["admissible"])

def preferred(arguments, attacks) -> List[FrozenSet[str]]:
    # enumerate admissible with clingo, pick ⊆-maximal in Python
    adm = admissible(arguments, attacks)
    return [S for S in adm if not any(S < T for T in adm)]

def credulous(fams: List[FrozenSet[str]], a: str) -> bool:
    return any(a in S for S in fams)

def skeptical(fams: List[FrozenSet[str]], a: str) -> bool:
    return bool(fams) and all(a in S for S in fams)

def export_dot(arguments: Iterable[str], attacks: Iterable[Tuple[str,str]], path: str) -> None:
    lines = ["digraph AF {"]
    for a in arguments:
        lines.append(f'  "{a}" [shape=ellipse,label="{a}"];')
    for (u, v) in sorted(attacks):
        lines.append(f'  "{u}" -> "{v}";')
    lines.append("}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ---------- CLI ----------
def _format_setset(sets: List[FrozenSet[str]]) -> str:
    if not sets: return "[]"
    return "[" + ", ".join("{" + ", ".join(sorted(S)) + "}" for S in sets) + "]"

def main():
    ap = argparse.ArgumentParser(description="Compute Dung semantics from an APX file using clingo.")
    ap.add_argument("apx", help="Path to APX file (arg/att facts).")
    ap.add_argument("--sem", default="all",
                    choices=["grounded","preferred","stable","complete","stage","semi-stable","semistable","all"],
                    help="Which semantics to compute (default: all).")
    ap.add_argument("--json", action="store_true", help="Output JSON.")
    ap.add_argument("--query", type=str, default=None, help="Atom to test for acceptance (e.g., a1).")
    ap.add_argument("--mode", type=str, default=None, choices=["credulous","skeptical"],
                    help="Query mode for --query.")
    ap.add_argument("--dot", type=str, default=None, help="Export DOT graph to this path.")
    args = ap.parse_args()

    atoms, atts = read_apx(args.apx)
    if args.dot:
        export_dot(atoms, atts, args.dot)

    # compute semantics
    if args.sem == "all":
        res = {
            "grounded": grounded(atoms, atts),
            "preferred": preferred(atoms, atts),
            "stable":    stable(atoms, atts),
            "complete":  complete(atoms, atts),
            "stage":     stage(atoms, atts),
            "semi-stable": semi_stable(atoms, atts),
        }
    elif args.sem == "grounded":
        res = grounded(atoms, atts)
    elif args.sem == "preferred":
        res = preferred(atoms, atts)
    elif args.sem == "stable":
        res = stable(atoms, atts)
    elif args.sem == "complete":
        res = complete(atoms, atts)
    elif args.sem == "stage":
        res = stage(atoms, atts)
    else:  # semi-stable / semistable
        res = semi_stable(atoms, atts)

    # query
    query_ans = None
    if args.query and args.mode:
        if args.sem == "grounded":
            fam = [res] if isinstance(res, frozenset) else [grounded(atoms, atts)]
        elif args.sem == "all":
            fam = preferred(atoms, atts)  # default family for queries
        else:
            fam = res if isinstance(res, list) else [res]
        query_ans = credulous(fam, args.query) if args.mode == "credulous" else skeptical(fam, args.query)

    # output
    if args.json:
        out = {
            "arguments": atoms,
            "attacks": sorted(list(atts)),
            "semantics": None
        }
        if args.sem == "all":
            out["semantics"] = {
                "grounded": sorted(list(res["grounded"])),
                "preferred": [sorted(list(S)) for S in res["preferred"]],
                "stable":    [sorted(list(S)) for S in res["stable"]],
                "complete":  [sorted(list(S)) for S in res["complete"]],
                "stage":     [sorted(list(S)) for S in res["stage"]],
                "semi-stable": [sorted(list(S)) for S in res["semi-stable"]],
            }
        else:
            if isinstance(res, frozenset):
                out["semantics"] = sorted(list(res))
            else:
                out["semantics"] = [sorted(list(S)) for S in res]
        if query_ans is not None:
            out["query"] = {"arg": args.query, "mode": args.mode, "answer": bool(query_ans)}
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # human-readable
    print("=== AF (from APX) ===")
    print("Arguments:", ", ".join(atoms) if atoms else "(none)")
    print("Attacks:")
    if not atts:
        print("  (none)")
    else:
        for (u, v) in sorted(atts):
            print(f"  {u} -> {v}")

    def _show(name: str, sets):
        if isinstance(sets, frozenset):
            print(f"{name}: "+"{" + ", ".join(sorted(list(sets))) + "}")
        else:
            print(f"{name}: " + _format_setset(sets))

    if args.sem == "all":
        print("\n=== Semantics ===")
        _show("Grounded", res["grounded"])
        _show("Preferred", res["preferred"])
        _show("Stable", res["stable"])
        _show("Complete", res["complete"])
        _show("Stage", res["stage"])
        _show("Semi-stable", res["semi-stable"])
    else:
        print(f"\n=== {args.sem.upper()} ===")
        _show(args.sem.capitalize(), res)

    if args.query and args.mode:
        print(f"\nQuery: {args.mode.capitalize()} acceptance of {args.query}: {'YES' if query_ans else 'NO'}")

if __name__ == "__main__":
    main()