from __future__ import annotations
import re
from .ast import *
def _san(s: str) -> str:
    s = re.sub(r'[^A-Za-z0-9_]', '_', s.strip()); return s or "x"
def term(t: Term) -> str:
    if isinstance(t, Var):
        n=_san(t.name); return n if n[0].isupper() else n[0].upper()+n[1:]
    n=_san(t.name); return n if n[0].islower() else n[0].lower()+n[1:]
def atom(a: Atom) -> str:
    pred=_san(a.pred.name); pred = pred if pred[0].islower() else pred[0].lower()+pred[1:]
    args=",".join(term(t) for t in a.args); s=f"{pred}({args})" if args else pred
    return f"~({s})" if a.negated else s
def formula(phi: Formula) -> str:
    if isinstance(phi, Atom): return atom(phi)
    if isinstance(phi, Not): return f"~({formula(phi.phi)})"
    if isinstance(phi, And): return f"({formula(phi.left)} & {formula(phi.right)})"
    if isinstance(phi, Or): return f"({formula(phi.left)} | {formula(phi.right)})"
    if isinstance(phi, Implies): return f"({formula(phi.left)} => {formula(phi.right)})"
    if isinstance(phi, Forall): v=term(phi.var); return f"! [{v}] : ({formula(phi.body)})"
    if isinstance(phi, Exists): v=term(phi.var); return f"? [{v}] : ({formula(phi.body)})"
    raise TypeError(type(phi))
def fof(name: str, role: str, phi: Formula) -> str:
    return f"fof({_san(name)}, {role}, {formula(phi)})."
