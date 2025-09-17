from __future__ import annotations
from typing import Dict, Any, Optional
import importlib
import json
from .normalize.canonicalize import canonicalize
from .checks.rules import run_all
from .checks.strict import strict_validate
from .semantics.semantics import compute_extensions
from .fol.translate import argir_to_fof
from .fol.eprover import call_eprover
from .report.render import to_markdown

def assert_not_all_goal_shape(soft_ir: dict, source_text: str) -> None:
    """Fail-fast invariant for 'not all' goals - no repairs, just validation."""
    txt = source_text.lower()
    if "not all" not in txt and "not every" not in txt:
        return

    goal_id = (soft_ir.get("goal") or {}).get("node_id")
    assert goal_id, "Not-all text present, but no GOAL node_id in soft IR"

    nodes = {n.get("id"): n for n in soft_ir.get("graph", {}).get("nodes", []) if n.get("id")}
    g = nodes.get(goal_id)
    assert g and "conclusion" in g, f"GOAL node {goal_id} must be a conclusion node for 'not all' text"

    concl = g["conclusion"]
    assert concl, "GOAL conclusion cannot be empty for 'not all' text"

    # Handle both list and single statement forms
    stmts = concl if isinstance(concl, list) else [concl]

    # Check for negated property - either via polarity or negated flag
    has_negation = False
    for s in stmts:
        if isinstance(s, dict):
            if s.get("polarity") == "neg":
                has_negation = True
                break
            # Also check atoms for strict format
            atoms = s.get("atoms", [])
            if any(a.get("negated", False) for a in atoms if isinstance(a, dict)):
                has_negation = True
                break

    # Check quantifiers (may be on conclusion or node level)
    q = (concl.get("quantifiers") if isinstance(concl, dict) else None) or g.get("quantifiers") or []
    assert any((isinstance(qq, dict) and qq.get("kind") == "exists") for qq in q), \
        "GOAL for 'not all' MUST use an ∃ quantifier"

    if not has_negation:
        # Warning instead of hard failure - extraction may be pre-optimizing
        print(f"Warning: 'not all' goal may be missing explicit negation in soft IR (pre-optimized?)")

def run_pipeline(text: str, fol_mode: str = "classical", goal_id: Optional[str] = None) -> Dict[str, Any]:
    parse_mod = importlib.import_module("argir.nlp.parse")
    draft, draft_meta = parse_mod.llm_draft(text)
    canon = canonicalize(draft)
    argir = canon.argir

    # Always run validation checks (as warnings)
    validation_issues = strict_validate(argir)

    fof_pairs = argir_to_fof(argir, fol_mode=fol_mode, goal_id=goal_id)
    fof_lines = [fof for _, fof in fof_pairs]
    try:
        semantics = compute_extensions(argir)
    except Exception as e:
        semantics = {"error": f"{type(e).__name__}: {e}"}
    fol_summary = call_eprover(fof_lines)
    findings = run_all(argir)

    # Include validation issues in warnings if strict mode is enabled
    all_warnings = {"warnings": canon.warnings}
    if validation_issues:
        all_warnings["validation_issues"] = validation_issues

    report_md = to_markdown(argir, findings, semantics, fol_summary, fof_lines, all_warnings)
    return {
        "argir": argir.model_dump(),
        "draft": draft,
        "findings": findings,
        "semantics": semantics,
        "fof": fof_lines,
        "fol_summary": fol_summary,
        "report_md": report_md,
        "validation_issues": validation_issues  # Include in result for UI to display
    }

def run_pipeline_soft(text: str, fol_mode: str = "classical", goal_id: Optional[str] = None, goal_hint: Optional[str] = None, k_samples: int = 1) -> Dict[str, Any]:
    """Run pipeline with soft IR extraction and compilation to strict ARGIR."""
    from .soft_ir import SoftIR, SoftGraph, SoftNode, SoftEdge, SoftStatement, SoftTerm, SoftRule, SoftPremiseRef
    from .compile_soft import compile_soft_ir
    from .validate import ValidationReport
    from .prompts import get_soft_extraction_prompt

    # Get LLM to produce soft IR
    parse_mod = importlib.import_module("argir.nlp.parse")
    llm = parse_mod.get_llm()

    system_prompt, user_prompt = get_soft_extraction_prompt(text, goal_hint)

    best_argir = None
    best_report = None
    best_draft = None
    min_errors = float('inf')

    # Try k samples and pick the best
    for i in range(k_samples):
        try:
            # Call LLM for soft extraction
            # Add sample index to user prompt when k > 1 to bypass cache
            if k_samples > 1:
                indexed_user_prompt = f"{user_prompt}\n<!-- Sample {i+1}/{k_samples} -->"
            else:
                indexed_user_prompt = user_prompt
            response = llm(system_prompt, indexed_user_prompt)

            # Parse response as JSON
            if isinstance(response, str):
                soft_data = json.loads(response)
            else:
                soft_data = response

            # Convert to SoftIR dataclasses
            nodes = []
            for n_data in soft_data.get("graph", {}).get("nodes", []):
                # Parse premises
                premises = []
                for p in n_data.get("premises", []):
                    if isinstance(p, dict):
                        if p.get("kind") == "Ref":
                            premises.append(SoftPremiseRef(ref=p.get("ref", "")))
                        else:
                            # It's a statement
                            args = [SoftTerm(value=a.get("value", "")) for a in p.get("args", [])]
                            premises.append(SoftStatement(
                                pred=p.get("pred", ""),
                                args=args,
                                polarity=p.get("polarity", "pos"),
                                quantifiers=p.get("quantifiers")  # Pass through quantifiers
                            ))

                # Parse rule if present
                rule = None
                if r_data := n_data.get("rule"):
                    def parse_stmts(stmt_list):
                        stmts = []
                        for s in stmt_list:
                            args = [SoftTerm(value=a.get("value", "")) for a in s.get("args", [])]
                            stmts.append(SoftStatement(
                                pred=s.get("pred", ""),
                                args=args,
                                polarity=s.get("polarity", "pos"),
                                quantifiers=s.get("quantifiers")  # Pass through quantifiers
                            ))
                        return stmts

                    rule = SoftRule(
                        name=r_data.get("name"),
                        strict=r_data.get("strict", False),
                        antecedents=parse_stmts(r_data.get("antecedents", [])),
                        consequents=parse_stmts(r_data.get("consequents", [])),
                        exceptions=parse_stmts(r_data.get("exceptions", []))
                    )

                # Parse conclusion if present
                conclusion = None
                if c_data := n_data.get("conclusion"):
                    args = [SoftTerm(value=a.get("value", "")) for a in c_data.get("args", [])]
                    conclusion = SoftStatement(
                        pred=c_data.get("pred", ""),
                        args=args,
                        polarity=c_data.get("polarity", "pos"),
                        quantifiers=c_data.get("quantifiers")  # Pass through quantifiers
                    )

                nodes.append(SoftNode(
                    id=n_data.get("id"),
                    premises=premises,
                    rule=rule,
                    conclusion=conclusion,
                    span=n_data.get("span"),
                    rationale=n_data.get("rationale")
                ))

            # Parse edges
            edges = [
                SoftEdge(
                    source=e.get("source", ""),
                    target=e.get("target", ""),
                    kind=e.get("kind", "support"),
                    attack_kind=e.get("attack_kind"),
                    rationale=e.get("rationale")
                )
                for e in soft_data.get("graph", {}).get("edges", [])
            ]

            soft_ir = SoftIR(
                version=soft_data.get("version", "soft-0.1"),
                source_text=text,  # Use original text
                graph=SoftGraph(nodes=nodes, edges=edges),
                metadata=soft_data.get("metadata", {}),
                goal=soft_data.get("goal")  # Pass through goal
            )

            # Apply LLM repairs to improve consistency
            from .repair import apply_llm_repairs

            # Create a simple LLM call wrapper using the same LLM instance
            def llm_call_wrapper(prompt: str) -> str:
                """Call LLM with minimal system prompt for repairs."""
                repair_system = "You are a helpful assistant that analyzes and repairs logical argument structures. Return only valid JSON."
                return llm(repair_system, prompt)

            # Apply repairs to the soft_data dict (before converting to dataclasses)
            # This is more efficient than converting back and forth
            apply_llm_repairs(soft_data, text, llm_call_wrapper)

            # Invariant check for "not all" patterns - fail fast, no repairs
            assert_not_all_goal_shape(soft_data, text)

            # Re-parse the repaired soft_data into dataclasses
            nodes = []
            for n_data in soft_data.get("graph", {}).get("nodes", []):
                # Parse premises
                premises = []
                for p in n_data.get("premises", []):
                    if isinstance(p, dict):
                        if p.get("kind") == "Ref":
                            premises.append(SoftPremiseRef(ref=p.get("ref", "")))
                        else:
                            # It's a statement
                            args = [SoftTerm(value=a.get("value", "")) for a in p.get("args", [])]
                            premises.append(SoftStatement(
                                pred=p.get("pred", ""),
                                args=args,
                                polarity=p.get("polarity", "pos"),
                                quantifiers=p.get("quantifiers")
                            ))

                # Parse rule if present
                rule = None
                if n_data.get("rule"):
                    r = n_data["rule"]
                    rule = SoftRule(
                        name=r.get("name"),
                        strict=r.get("strict", False),
                        antecedents=[
                            SoftStatement(
                                pred=s.get("pred", ""),
                                args=[SoftTerm(value=a.get("value", "")) for a in s.get("args", [])],
                                polarity=s.get("polarity", "pos"),
                                quantifiers=s.get("quantifiers")
                            )
                            for s in r.get("antecedents", [])
                        ],
                        consequents=[
                            SoftStatement(
                                pred=s.get("pred", ""),
                                args=[SoftTerm(value=a.get("value", "")) for a in s.get("args", [])],
                                polarity=s.get("polarity", "pos"),
                                quantifiers=s.get("quantifiers")
                            )
                            for s in r.get("consequents", [])
                        ],
                        exceptions=[
                            SoftStatement(
                                pred=s.get("pred", ""),
                                args=[SoftTerm(value=a.get("value", "")) for a in s.get("args", [])],
                                polarity=s.get("polarity", "pos"),
                                quantifiers=s.get("quantifiers")
                            )
                            for s in r.get("exceptions", [])
                        ]
                    )

                # Parse conclusion if present
                conclusion = None
                if n_data.get("conclusion"):
                    c = n_data["conclusion"]
                    conclusion = SoftStatement(
                        pred=c.get("pred", ""),
                        args=[SoftTerm(value=a.get("value", "")) for a in c.get("args", [])],
                        polarity=c.get("polarity", "pos"),
                        quantifiers=c.get("quantifiers")
                    )

                nodes.append(SoftNode(
                    id=n_data.get("id"),
                    premises=premises,
                    rule=rule,
                    conclusion=conclusion,
                    span=n_data.get("span"),
                    rationale=n_data.get("rationale")
                ))

            # Re-create edges
            edges = [
                SoftEdge(
                    source=e.get("source", ""),
                    target=e.get("target", ""),
                    kind=e.get("kind", "support"),
                    attack_kind=e.get("attack_kind"),
                    rationale=e.get("rationale")
                )
                for e in soft_data.get("graph", {}).get("edges", [])
            ]

            # Create repaired SoftIR
            soft_ir = SoftIR(
                version=soft_data.get("version", "soft-0.1"),
                source_text=text,
                graph=SoftGraph(nodes=nodes, edges=edges),
                metadata=soft_data.get("metadata", {}),
                goal=soft_data.get("goal")
            )

            # Compile to strict ARGIR (pass goal_id to override auto-detection)
            argir_dict, atom_table, validation_report = compile_soft_ir(soft_ir, goal_id=goal_id)

            # Count errors
            error_count = len(validation_report.errors())

            # Keep best candidate
            if error_count < min_errors:
                min_errors = error_count
                best_argir = argir_dict
                best_report = validation_report
                best_draft = soft_data

                # If we have a perfect result, stop early
                if error_count == 0:
                    break

        except Exception as e:
            # Log but continue with other samples
            print(f"Sample {i+1} failed: {e}")
            continue

    if best_argir is None:
        raise ValueError("Failed to generate valid ARGIR from any sample")

    # Continue with rest of pipeline using the compiled ARGIR
    from .core.model import ARGIR
    argir_obj = ARGIR.model_validate(best_argir)

    # Run the rest of the pipeline as normal
    fof_pairs = argir_to_fof(argir_obj, fol_mode=fol_mode, goal_id=goal_id)
    fof_lines = [fof for _, fof in fof_pairs]

    try:
        semantics = compute_extensions(argir_obj)
    except Exception as e:
        semantics = {"error": f"{type(e).__name__}: {e}"}

    fol_summary = call_eprover(fof_lines)
    findings = run_all(argir_obj)

    # Prepare warnings
    all_warnings = {"soft_validation": [i.__dict__ for i in best_report.issues]}

    report_md = to_markdown(argir_obj, findings, semantics, fol_summary, fof_lines, all_warnings)

    return {
        "argir": best_argir,
        "draft": best_draft,
        "findings": findings,
        "semantics": semantics,
        "fof": fof_lines,
        "fol_summary": fol_summary,
        "report_md": report_md,
        "soft_validation": best_report
    }
