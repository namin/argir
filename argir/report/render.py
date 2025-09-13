from __future__ import annotations
from typing import List, Dict, Any, Optional
from ..core.model import ARGIR, Statement, NodeRef

def _span_snip(src: str, span) -> str:
    if not span: return ""
    try:
        s = max(0, int(span.start)); e = min(len(src), int(span.end))
        return src[s:e].replace("\n"," ")
    except Exception: return ""

def _fmt_stmt(src: str, s: Optional[Statement]) -> str:
    if not s: return "*none*"
    atoms = "; ".join((("¬" if a.negated else "") + a.pred + "(" + ", ".join(f"{t.kind}:{t.name}" for t in a.args) + ")") for a in (s.atoms or [])) or "—"
    q = ", ".join(f"{qq.kind} {qq.var}" + (f":{qq.sort}" if qq.sort else "") for qq in (s.quantifiers or [])) or "—"
    conf = "unknown" if s.confidence is None else f"{s.confidence:.2f}"
    snip = _span_snip(src, s.span)
    rat = s.rationale or ""
    return f"- text: **{s.text}**\n  - atoms: {atoms}\n  - quantifiers: {q}\n  - confidence: {conf}\n  - span: “{snip}”\n  - rationale: {rat}"

def to_markdown(u: ARGIR, findings: List[dict], semantics: dict|None, fol_summary: dict|None, fof_lines: List[str], parse_info: Dict[str,Any]) -> str:
    src = u.source_text or ""
    lines: List[str] = []
    lines.append("# ARGIR Report\n")
    lines.append("## Source Text\n")
    lines.append("```"); lines.append(src); lines.append("```\n")
    try:
        lex = None
        if u.metadata:
            if isinstance(u.metadata.get("atom_lexicon"), dict):
                lex = u.metadata["atom_lexicon"]
            elif isinstance(u.metadata.get("symbols"), dict) and isinstance(u.metadata["symbols"].get("predicates"), dict):
                lex = u.metadata["symbols"]["predicates"]
    except Exception:
        lex = None
    if isinstance(lex, dict) and lex:
        lines.append("## Atom Lexicon (canonical → examples)\n")
        for k, v in lex.items():
            if isinstance(v, (list, tuple)):
                vv = ", ".join(str(x) for x in v)
            else:
                vv = str(v)
            lines.append(f"- `{k}`: {vv}")
        lines.append("")
    lines.append("## Nodes (Structured Steps)\n")
    for n in u.graph.nodes:
        lines.append(f"### Node `{n.id}`")
        snip = _span_snip(src, n.span)
        if snip: lines.append(f"_Span:_ “{snip}”")
        lines.append("**Premises**")
        if n.premises:
            for p in n.premises:
                if isinstance(p, NodeRef):
                    lines.append(f"- ref: **{p.ref}**")
                else:
                    lines.append(_fmt_stmt(src, p))
        else:
            lines.append("*none*")
        lines.append("\n**Rule**")
        if n.rule:
            r = n.rule
            lines.append(f"- name: `{r.name}`")
            lines.append(f"  - strict: {r.strict}")
            lines.append(f"  - scheme: {r.scheme or '—'}")
            if r.antecedents:
                lines.append("  - antecedents:")
                for s in r.antecedents: lines.append("    " + _fmt_stmt(src, s).replace("\n","\n    "))
            if r.consequents:
                lines.append("  - consequents:")
                for s in r.consequents: lines.append("    " + _fmt_stmt(src, s).replace("\n","\n    "))
            if r.exceptions:
                lines.append("  - exceptions:")
                for s in r.exceptions: lines.append("    " + _fmt_stmt(src, s).replace("\n","\n    "))
        else:
            lines.append("*none*")
        lines.append("\n**Conclusion**")
        lines.append(_fmt_stmt(src, n.conclusion))
        if n.rationale: lines.append(f"\n**Node rationale:** {n.rationale}")
        lines.append("")
    lines.append("## Edges (Argumentation Graph)\n")
    for e in u.graph.edges:
        tag = f"[{e.kind}{('/'+e.attack_kind) if e.attack_kind else ''}]"
        lines.append(f"- `{e.source}` → `{e.target}` **{tag}** — {e.rationale or ''}")
    lines.append("\n## Coherence Findings\n")
    if findings:
        for f in findings: lines.append(f"- **{f.get('kind','finding')}**: {f.get('message', f)}")
    else:
        lines.append("- (none)")
    if semantics:
        import json as _j
        lines.append("\n## AF Semantics\n```"); lines.append(_j.dumps(semantics, indent=2)); lines.append("```")
    if fof_lines:
        lines.append("\n## FOL (FOF) Axioms\n```"); lines += fof_lines; lines.append("```")
    if fol_summary:
        import json as _j
        lines.append("\n## FOL Summary (E-prover)\n```"); lines.append(_j.dumps(fol_summary, indent=2)); lines.append("```")
    import json as _j
    lines.append("\n## Appendix: Canonical ARGIR (JSON)\n```json"); lines.append(_j.dumps(u.model_dump(), indent=2)); lines.append("```")
    return "\n".join(lines)
