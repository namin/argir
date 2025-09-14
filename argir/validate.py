# argir/validate.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class Issue:
    code: str         # e.g., "MISSING_LEXICON", "DANGLING_REF", "ARITY_MISMATCH"
    path: str         # JSONPath-ish (e.g., "graph.nodes[3].conclusion")
    message: str
    severity: str = "error"
    fix_applied: bool = False

@dataclass
class ValidationReport:
    issues: List[Issue]
    def errors(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "error" and not i.fix_applied]
    def warn(self) -> List[Issue]:
        return [i for i in self.issues if i.severity == "warning" and not i.fix_applied]

# Minimal patchers (deterministic)
def patch_missing_lexicon(report: ValidationReport, argir_obj: dict) -> None:
    """If metadata.atom_lexicon missing but every node has canonical preds, synthesize it."""
    md = argir_obj.setdefault("metadata", {})
    if "atom_lexicon" not in md:
        # Walk predicates and infer arities from usage.
        preds = {}
        for n in argir_obj.get("graph", {}).get("nodes", []):
            # Check conclusion
            if c := n.get("conclusion"):
                if isinstance(c, dict) and c.get("kind") == "Stmt":
                    for atom in c.get("atoms", []):
                        p = atom.get("pred")
                        a = len(atom.get("args", []))
                        if p:
                            preds.setdefault(p, set()).add(a)
            # Check premises
            for pr in n.get("premises", []):
                if isinstance(pr, dict) and pr.get("kind") == "Stmt":
                    for atom in pr.get("atoms", []):
                        p = atom.get("pred")
                        a = len(atom.get("args", []))
                        if p:
                            preds.setdefault(p, set()).add(a)
            # Check rules
            if r := n.get("rule"):
                for stmts in [r.get("antecedents", []), r.get("consequents", []), r.get("exceptions", [])]:
                    for st in stmts:
                        if isinstance(st, dict) and st.get("kind") == "Stmt":
                            for atom in st.get("atoms", []):
                                p = atom.get("pred")
                                a = len(atom.get("args", []))
                                if p:
                                    preds.setdefault(p, set()).add(a)

        # Keep only well-defined (single-arity) preds
        lex = {}
        for p, arities in preds.items():
            if len(arities) == 1:
                lex[p] = [p]  # Use predicate itself as example
            else:
                report.issues.append(Issue(
                    code="MULTI_ARITY_PRED", path=f"metadata.atom_lexicon.{p}",
                    message=f"Predicate {p} used with multiple arities: {sorted(arities)}",
                    severity="warning"))
        if lex:
            md["atom_lexicon"] = lex
            # Mark as fixed
            for issue in report.issues:
                if issue.code == "MISSING_LEXICON":
                    issue.fix_applied = True

def validate_argir(argir_obj: dict) -> ValidationReport:
    """Validate ARGIR object against strict contract."""
    issues: List[Issue] = []
    md = argir_obj.get("metadata", {})
    lex = md.get("atom_lexicon", {})

    # 0) Check if lexicon exists
    if not lex:
        issues.append(Issue("MISSING_LEXICON", "metadata.atom_lexicon",
                          "atom_lexicon is missing or empty"))

    # 1) Lexicon membership - check all atoms against lexicon
    for ni, n in enumerate(argir_obj.get("graph", {}).get("nodes", [])):
        def check_stmt(stmt, path):
            if isinstance(stmt, dict) and stmt.get("kind") == "Stmt":
                for ai, atom in enumerate(stmt.get("atoms", [])):
                    p = atom.get("pred")
                    if p and p not in lex:
                        issues.append(Issue("MISSING_LEXICON",
                                          f"{path}.atoms[{ai}]",
                                          f"Predicate '{p}' not in atom_lexicon"))

        # Check conclusion
        if c := n.get("conclusion"):
            check_stmt(c, f"graph.nodes[{ni}].conclusion")

        # Check premises
        for pi, pr in enumerate(n.get("premises", [])):
            if isinstance(pr, dict) and pr.get("kind") != "Ref":
                check_stmt(pr, f"graph.nodes[{ni}].premises[{pi}]")

        # Check rule statements
        if r := n.get("rule"):
            for si, st in enumerate(r.get("antecedents", [])):
                check_stmt(st, f"graph.nodes[{ni}].rule.antecedents[{si}]")
            for si, st in enumerate(r.get("consequents", [])):
                check_stmt(st, f"graph.nodes[{ni}].rule.consequents[{si}]")
            for si, st in enumerate(r.get("exceptions", [])):
                check_stmt(st, f"graph.nodes[{ni}].rule.exceptions[{si}]")

    # 2) Dangling refs (sources/targets and premise refs)
    node_ids = {n.get("id") for n in argir_obj.get("graph", {}).get("nodes", [])}
    for ni, n in enumerate(argir_obj.get("graph", {}).get("nodes", [])):
        for pi, pr in enumerate(n.get("premises", [])):
            if isinstance(pr, dict) and pr.get("kind") == "Ref":
                if pr.get("ref") not in node_ids:
                    issues.append(Issue("DANGLING_REF",
                        f"graph.nodes[{ni}].premises[{pi}]",
                        f"Unknown ref '{pr.get('ref')}'"))

    for ei, e in enumerate(argir_obj.get("graph", {}).get("edges", [])):
        for side in ("source", "target"):
            if e.get(side) not in node_ids:
                issues.append(Issue("DANGLING_REF",
                    f"graph.edges[{ei}].{side}",
                    f"Unknown node '{e.get(side)}'"))

    return ValidationReport(issues=issues)