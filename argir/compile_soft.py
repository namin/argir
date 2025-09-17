# argir/compile_soft.py
from __future__ import annotations
from typing import Dict, List, Tuple
import re
from .soft_ir import SoftIR, SoftNode, SoftStatement, SoftPremiseRef, SoftTerm, SoftRule
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


def _split_conjunctions(antecedents: List[dict], max_conjuncts: int = 3) -> List[dict]:
    """
    Split conjunctions in antecedents when possible.
    E.g., "P1 and P2" becomes two separate antecedents.
    """
    result = []
    for ant in antecedents:
        # Check if text contains "and" coordination
        text = ant.get("text", "")
        if " and " in text.lower() and len(ant.get("atoms", [])) > 1:
            # Split atoms across separate antecedents (up to max_conjuncts)
            atoms = ant.get("atoms", [])[:max_conjuncts]
            for atom in atoms:
                new_ant = dict(ant)
                new_ant["atoms"] = [atom]
                new_ant["text"] = f"Split conjunct: {atom.get('pred', '')}"
                result.append(new_ant)
        else:
            result.append(ant)
    return result

def _canon_stmt(stmt: SoftStatement, at: AtomTable) -> Tuple[str, int, dict]:
    pred, extracted_entities = at.propose(stmt.pred, observed_arity=len(stmt.args))
    # Convert to ARGIR statement format with atoms
    # Args must be Term objects with kind and name fields - now preserving variables
    args = [_mk_term(t.value) for t in stmt.args]

    # Transform soft quantifiers to strict ARGIR format
    # Soft format: [{"kind": "exists", "vars": ["X", "Y"]}]
    # Strict format: [{"kind": "exists", "var": "X"}, {"kind": "exists", "var": "Y"}]
    soft_qs = getattr(stmt, "quantifiers", None) or []
    qs = []
    for q in soft_qs:
        if isinstance(q, dict):
            kind = q.get("kind", "forall")
            vars_list = q.get("vars", [])
            # Create individual Quantifier objects for each variable
            for var in vars_list:
                qs.append({"kind": kind, "var": var})
        # If it's already in the right format, keep it
        elif hasattr(q, "kind") and hasattr(q, "var"):
            qs.append({"kind": q.kind, "var": q.var})

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
        "quantifiers": qs,
        "span": None,
        "rationale": None,
        "confidence": None
    }
    return pred, len(args), obj

def compile_soft_ir(soft: SoftIR, *, existing_atoms: AtomTable | None = None, goal_id: str | None = None) -> Tuple[Dict, AtomTable, "ValidationReport"]:
    """Return a canonical ARGIR object (JSON-safe dict) that satisfies the hard contract.

    Args:
        soft: The soft IR to compile
        existing_atoms: Optional atom table to use/extend
        goal_id: Explicit goal ID to use (overrides auto-detection)
    """
    from .validate import validate_argir, patch_missing_lexicon

    at = existing_atoms or AtomTable()

    # ID assignment first
    idmap = _assign_ids(soft.graph.nodes)

    # Build hard nodes
    hard_nodes: List[dict] = []
    for n in soft.graph.nodes:
        hard = {"id": idmap.get(n.id, n.id), "premises": []}

        # Canonicalize fact nodes: premise-only nodes with no conclusion/rule
        # Convert them to proper fact nodes (empty premises, fact in conclusion)
        if (not n.rule and not n.conclusion and n.premises and
            all(not isinstance(p, SoftPremiseRef) for p in n.premises)):
            # This is a fact assertion node - move premises to conclusion
            if len(n.premises) == 1:
                # Single fact - move it to conclusion
                n.conclusion = n.premises[0]
                n.premises = []
                # Add a "Given" rule to mark it as a fact
                n.rule = SoftRule(name="Given", strict=True)
            # Note: could handle multiple facts as conjunction here if needed

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
            # Determine appropriate scheme based on rule type
            if n.rule.name == "Given":
                scheme = "Fact"
            else:
                scheme = "If A then B"  # Default scheme

            hard["rule"] = {
                "name": n.rule.name or "Conditional",
                "strict": n.rule.strict,
                "antecedents": ants,
                "consequents": cons,
                "exceptions": excs,
                "scheme": scheme
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
            # Find the span text in the source text to get real indices
            span_text = n.span
            start_idx = soft.source_text.find(span_text)

            # If not found, try case-insensitive search
            if start_idx == -1:
                lower_source = soft.source_text.lower()
                lower_span = span_text.lower()
                start_idx = lower_source.find(lower_span)
                if start_idx != -1:
                    # Extract the actual text from source with original casing
                    span_text = soft.source_text[start_idx:start_idx + len(span_text)]

            # If still not found, try removing common prefixes like "But "
            if start_idx == -1:
                for prefix in ["But ", "However, ", "Therefore, ", "So, ", "Thus, "]:
                    if soft.source_text.find(prefix + span_text) != -1:
                        start_idx = soft.source_text.find(prefix + span_text)
                        span_text = prefix + span_text
                        break

            if start_idx != -1:
                # Found the text in the source
                hard["span"] = {
                    "start": start_idx,
                    "end": start_idx + len(span_text),
                    "text": span_text
                }
            else:
                # Fallback: if we can't find exact match, store in rationale
                if n.rationale:
                    hard["rationale"] = f"[Source: \"{n.span}\"] {n.rationale}"
                else:
                    hard["rationale"] = f"Source: \"{n.span}\""
        if n.rationale and "rationale" not in hard:
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

            # Split conjunctions if possible (max 3 conjuncts)
            split_antecedents = _split_conjunctions(antecedents, max_conjuncts=3)

            # Create implicit rule node
            implicit_rule = {
                "id": rule_id,
                "premises": [],
                "rule": {
                    "name": "implicit_inference",
                    "strict": False,  # Default to defeasible
                    "antecedents": split_antecedents,
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

    # Auto-generate edges from node references if not already present
    # When a node references another node via {"kind": "Ref", "ref": "node_id"},
    # create a support edge from the referenced node to the current node
    existing_edges = {(e["source"], e["target"]) for e in hard_edges}

    for node in hard_nodes:
        target_id = node["id"]
        for premise in node.get("premises", []):
            if isinstance(premise, dict) and premise.get("kind") == "Ref":
                source_id = premise["ref"]
                # Check if this edge already exists
                if (source_id, target_id) not in existing_edges:
                    hard_edges.append({
                        "source": source_id,
                        "target": target_id,
                        "kind": "support",
                        "rationale": "Premise"
                    })
                    existing_edges.add((source_id, target_id))

    # Handle goal - explicit parameter takes precedence
    final_goal_id = None
    if goal_id:
        # Use explicitly provided goal_id (map it through idmap if needed)
        final_goal_id = idmap.get(goal_id, goal_id)
    else:
        # Auto-detect from soft IR
        if hasattr(soft, 'goal') and soft.goal:
            if isinstance(soft.goal, dict):
                old_goal_id = soft.goal.get('node_id')
                # Map the goal ID through the ID mapping
                final_goal_id = idmap.get(old_goal_id, old_goal_id)

        # Check metadata as fallback (including legacy goal_candidate_id)
        if not final_goal_id and hasattr(soft, 'metadata') and isinstance(soft.metadata, dict):
            old_goal_id = soft.metadata.get('goal_id') or soft.metadata.get('goal_candidate_id')
            if old_goal_id:
                final_goal_id = idmap.get(old_goal_id, old_goal_id)

    # Compose strict ARGIR object
    # Get lexicon in the format expected by validator (simple pred -> examples dict)
    full_lexicon = at.to_lexicon()
    simple_lexicon = {}
    if isinstance(full_lexicon, dict):
        # Extract just the surface forms for validator
        if "surface_forms" in full_lexicon:
            simple_lexicon = full_lexicon["surface_forms"]
        else:
            # Fallback: use predicates dict
            for pred in full_lexicon.get("predicates", {}):
                simple_lexicon[pred] = [pred]

    metadata = {
        # Provide lexicon in format expected by validator
        "atom_lexicon": simple_lexicon,
        # Also keep full lexicon for abduction
        "full_atom_lexicon": full_lexicon,
        "implicit_rules_synthesized": len(implicit_rules) > 0
    }

    # Add goal_id to metadata if present
    if final_goal_id:
        metadata["goal_id"] = final_goal_id

    argir_obj = {
        "version": soft.version or "0.3.2",
        "source_text": soft.source_text,
        "graph": {"nodes": hard_nodes, "edges": hard_edges},
        "metadata": metadata
    }

    # Validate + deterministic patchers
    report = validate_argir(argir_obj)
    if any(i.code == "MISSING_LEXICON" for i in report.issues):
        patch_missing_lexicon(report, argir_obj)
        report = validate_argir(argir_obj)

    return argir_obj, at, report