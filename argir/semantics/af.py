from __future__ import annotations
from typing import Set
from ..core.model import ARGIR
def af_projection(argir: ARGIR) -> tuple[list[str], list[tuple[str,str]]]:
    args: Set[str] = {n.id for n in argir.graph.nodes}
    att: list[tuple[str,str]] = []
    for e in argir.graph.edges:
        if e.kind == "attack":
            att.append((e.source, e.target))
    return sorted(args), att
def to_apx(arguments: list[str], attacks: list[tuple[str,str]]) -> str:
    lines = [f"arg({a})." for a in arguments]
    lines += [f"att({s},{t})." for (s,t) in attacks]
    return "\n".join(lines) + "\n"
