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

    # --- Goal & Proof Status ---
    goal_id = (u.metadata or {}).get("goal_id") or (u.metadata or {}).get("goal_candidate_id") or ""
    goal_line = ""
    if fof_lines:
        for ln in fof_lines:
            s = (ln or "").strip()
            if s.startswith("fof(goal"):
                goal_line = s; break
    # components count
    def _comps():
        ids = [n.id for n in u.graph.nodes]
        nbr = {i:set() for i in ids}
        for e in u.graph.edges:
            if e.source in nbr and e.target in nbr:
                nbr[e.source].add(e.target); nbr[e.target].add(e.source)
        seen=set(); k=0
        for i in ids:
            if i in seen: continue
            k+=1; st=[i]
            while st:
                x=st.pop()
                if x in seen: continue
                seen.add(x); st.extend(nbr[x])
        return k
    lines.append("## Goal & Proof Status\n")
    if goal_id: lines.append(f"**Goal node:** `{goal_id}`")
    if goal_line: lines.append(f"**FOL target:** `{goal_line}`")
    if fol_summary:
        status = "Unknown"
        if fol_summary.get("theorem"): status = "✓ Conjecture proved"
        elif fol_summary.get("unsat"): status = "Unsatisfiable"
        elif fol_summary.get("sat"): status = "Satisfiable"
        elif fol_summary.get("note"): status = fol_summary["note"]
        lines.append(f"**E‑Prover:** {status}")
    try:
        ncomp = _comps()
        if ncomp > 1:
            lines.append(f"**Note:** Graph has {ncomp} connected components; focusing on the GOAL component below.")
    except Exception: pass

    # --- Reconstructed Proof Sketch (support-only, goal component) ---
    # Build incoming/outgoing support maps
    id2 = {n.id: n for n in u.graph.nodes}
    inc = {n.id: [] for n in u.graph.nodes}
    out = {n.id: [] for n in u.graph.nodes}
    for e in u.graph.edges:
        if e.kind == "support":
            inc[e.target].append(e.source)
            out[e.source].append(e.target)
    # find goal component (undirected)
    comp = set()
    if goal_id and goal_id in id2:
        stack=[goal_id]
        while stack:
            x=stack.pop()
            if x in comp: continue
            comp.add(x)
            for y in inc.get(x, []): stack.append(y)
            for y in out.get(x, []): stack.append(y)
    else:
        comp = set(id2.keys())
    # topo over support inside component
    indeg = {i: sum(1 for _ in inc[i] if _ in comp) for i in comp}
    Q = [i for i in comp if indeg[i]==0]
    seen=set(); steps=[]
    def fmt_stmt(s):  # very light formatter
        if not s or not s.atoms: return s.text or "—"
        return " ∧ ".join(("¬" if a.negated else "") + a.pred + ("(" + ",".join(t.name for t in a.args) + ")" if a.args else "")
                           for a in s.atoms)
    while Q:
        cur = Q.pop(0)
        if cur in seen: continue
        seen.add(cur)
        n = id2[cur]
        if not n.premises and not n.rule and n.conclusion:
            steps.append(("Premise", cur, fmt_stmt(n.conclusion)))
        elif n.rule and not n.conclusion:
            name = (n.rule.name or n.rule.scheme or "rule")
            steps.append(("Rule", cur, f"{name}: ..."))
        elif n.conclusion:
            srcs = [s for s in inc.get(cur, []) if s in comp]
            name = (n.rule.name or n.rule.scheme or "rule") if n.rule else "inference"
            steps.append(("Derived", cur, f"From {', '.join(srcs)} by {name}, infer {fmt_stmt(n.conclusion)}"))
        for y in out.get(cur, []):
            if y in indeg:
                indeg[y]-=1
                if indeg[y]==0: Q.append(y)
    if steps:
        lines.append("\n## Proof sketch (goal component)\n")
        for i,(k,nid,txt) in enumerate(steps, 1):
            lines.append(f"{i}. *{k}* — {txt}")

    lines.append("\n## Source Text\n")
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

    # Add validation issues section if present
    if parse_info.get("validation_issues"):
        lines.append("\n## ⚠️ Validation Issues\n")
        lines.append("The following potential issues were detected in the argument structure:\n")
        for issue in parse_info["validation_issues"]:
            lines.append(f"- **Node `{issue['node']}`**: {issue['message']}")
        lines.append("\n*These are warnings about potentially incomplete reasoning but do not prevent processing.*")
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
