# argir/compile_soft.py
from __future__ import annotations
from typing import Dict, List, Tuple
import re
from .soft_ir import SoftIR, SoftNode, SoftStatement, SoftPremiseRef, SoftTerm
from .canonicalize import AtomTable

# Variable detection pattern - only specific variable names (X, Y, Z, W, U, V) with optional digits
# This avoids treating proper nouns (Socrates, USA, AI) as variables
VAR_RE = re.compile(r'^[XYZWUV]\d*$')  # X, Y, Z, W, U, V + optional digits like X1, Y2

def _assign_ids(nodes: List[SoftNode]) -> Dict[str, str]:
    """Map provisional node ids (or None) to stable IDs (C#, R#, P#).
    Heuristic: rule-backed nodes => 'R', conclusion-only => 'C', others => 'P'."""
    counters = {"R": 0, "C": 0, "P": 0}
    mapping: Dict[str, str] = {}
    def fresh(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}{counters[prefix]}"
    for n in nodes:
        old = n.id or ""
        if n.rule:
            new = fresh("R")
        elif n.conclusion and not n.premises:
            new = fresh("C")
        else:
            new = fresh("P")
        if old:
            mapping[old] = new
        else:
            mapping[f"_anon_{id(n)}"] = new
            n.id = f"_anon_{id(n)}"
    return mapping

def _mk_term(token: str) -> dict:
    """Create a term dict, detecting variables vs constants."""
    if VAR_RE.match(token):
        return {"kind": "Var", "name": token}
    return {"kind": "Const", "name": token}

def _canon_stmt(stmt: SoftStatement, at: AtomTable) -> Tuple[str, int, dict]:
    pred, extracted_entities = at.propose(stmt.pred, observed_arity=len(stmt.args))
    # Convert to ARGIR statement format with atoms
    # Args must be Term objects with kind and name fields - now preserving variables
    args = [_mk_term(t.value) for t in stmt.args]

    # Prepend extracted entities as arguments (always constants)
    if extracted_entities:
        entity_args = [{"kind": "Const", "name": e} for e in extracted_entities]
        args = entity_args + args

    obj = {
        "kind": "Stmt",
        "text": stmt.pred,  # Keep original text for provenance
        "atoms": [{
            "pred": pred,
            "args": args,
            "negated": stmt.polarity == "neg"
        }],
        "quantifiers": [],  # Will be quantified at FOL-lowering time
        "span": None,
        "rationale": None,
        "confidence": None
    }
    return pred, len(args), obj

def compile_soft_ir(soft: SoftIR, *, existing_atoms: AtomTable | None = None) -> Tuple[Dict, AtomTable, "ValidationReport"]:
    """Return a canonical ARGIR object (JSON-safe dict) that satisfies the hard contract."""
    from .validate import validate_argir, patch_missing_lexicon

    at = existing_atoms or AtomTable()

    # ID assignment first
    idmap = _assign_ids(soft.graph.nodes)

    # Build hard nodes
    hard_nodes: List[dict] = []
    for n in soft.graph.nodes:
        hard = {"id": idmap.get(n.id, n.id), "premises": []}
        if n.rule:
            # Canonicalize rule statements
            ants, cons, excs = [], [], []
            for a in n.rule.antecedents:
                _, _, obj = _canon_stmt(a, at)
                ants.append(obj)
            for c in n.rule.consequents:
                _, _, obj = _canon_stmt(c, at)
                cons.append(obj)
            for x in n.rule.exceptions:
                _, _, obj = _canon_stmt(x, at)
                excs.append(obj)
            hard["rule"] = {
                "name": n.rule.name or "Conditional",
                "strict": n.rule.strict,
                "antecedents": ants,
                "consequents": cons,
                "exceptions": excs,
                "scheme": "If A then B"  # Default scheme
            }
        if n.conclusion:
            _, _, cobj = _canon_stmt(n.conclusion, at)
            hard["conclusion"] = cobj
        for p in n.premises:
            if isinstance(p, SoftPremiseRef):
                hard["premises"].append({"kind": "Ref", "ref": idmap.get(p.ref, p.ref)})
            elif isinstance(p, SoftStatement):  # Explicit type check
                _, _, pobj = _canon_stmt(p, at)
                hard["premises"].append(pobj)
        if n.span:
            hard["span"] = n.span
        if n.rationale:
            hard["rationale"] = n.rationale
        hard_nodes.append(hard)

    # Auto-synthesize implicit rules for nodes with premises+conclusion but no rule
    implicit_rules = []
    for node in hard_nodes:
        if (node.get("premises") and node.get("conclusion") and
            not node.get("rule") and
            not any(p.get("kind") == "Ref" for p in node.get("premises", []) if isinstance(p, dict))):
            # This node needs an implicit rule
            rule_id = f"IR_{node['id']}"  # Implicit Rule for node

            # Extract antecedents from premises (only Statements, not Refs)
            antecedents = [p for p in node["premises"] if isinstance(p, dict) and p.get("kind") == "Stmt"]

            # Create implicit rule node
            implicit_rule = {
                "id": rule_id,
                "premises": [],
                "rule": {
                    "name": "implicit_inference",
                    "strict": False,  # Default to defeasible
                    "antecedents": antecedents,
                    "consequents": [node["conclusion"]],
                    "exceptions": [],
                    "scheme": "Implicit inference"
                },
                "rationale": f"Implicit rule for inference in node {node['id']}"
            }
            implicit_rules.append(implicit_rule)

            # Update the original node to reference this rule
            node["premises"].insert(0, {"kind": "Ref", "ref": rule_id})

    # Add implicit rules to nodes
    hard_nodes.extend(implicit_rules)

    # Build hard edges with remapped ids
    hard_edges = [{"source": idmap.get(e.source, e.source),
                   "target": idmap.get(e.target, e.target),
                   "kind": e.kind,
                   **({"attack_kind": e.attack_kind} if e.attack_kind else {}),
                   **({"rationale": e.rationale} if e.rationale else {})}
                  for e in soft.graph.edges]

    # Compose strict ARGIR object
    argir_obj = {
        "version": soft.version or "0.3.2",
        "source_text": soft.source_text,
        "graph": {"nodes": hard_nodes, "edges": hard_edges},
        "metadata": {
            # Provide lexicon deterministically to satisfy the contract
            "atom_lexicon": at.to_lexicon(),
            "implicit_rules_synthesized": len(implicit_rules) > 0
        }
    }

    # Validate + deterministic patchers
    report = validate_argir(argir_obj)
    if any(i.code == "MISSING_LEXICON" for i in report.issues):
        patch_missing_lexicon(report, argir_obj)
        report = validate_argir(argir_obj)

    return argir_obj, at, report