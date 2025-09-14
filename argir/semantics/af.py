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
    """Generate APX format for display/debugging (unquoted)."""
    lines = [f"arg({a})." for a in arguments]
    lines += [f"att({s},{t})." for (s,t) in attacks]
    return "\n".join(lines) + "\n"

def to_apx_for_clingo(arguments: list[str], attacks: list[tuple[str,str]]) -> str:
    """Generate APX format for clingo processing (with proper quoting).

    In ASP/clingo, identifiers starting with uppercase are variables,
    so we quote them to make them constants.
    """
    def quote_if_needed(s: str) -> str:
        # Quote if starts with uppercase (would be interpreted as variable)
        return f'"{s}"' if s and s[0].isupper() else s

    lines = [f"arg({quote_if_needed(a)})." for a in arguments]
    lines += [f"att({quote_if_needed(s)},{quote_if_needed(t)})." for (s,t) in attacks]
    return "\n".join(lines) + "\n"
