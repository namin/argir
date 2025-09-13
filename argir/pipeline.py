from __future__ import annotations
from typing import Dict, Any, Optional
import importlib
import os
from .normalize.canonicalize import canonicalize
from .checks.rules import run_all
from .checks.strict import strict_validate
from .semantics.semantics import compute_extensions
from .fol.translate import argir_to_fof
from .fol.eprover import call_eprover
from .report.render import to_markdown

def run_pipeline(text: str, fol_mode: str = "classical", goal_id: Optional[str] = None, *, strict: Optional[bool] = None) -> Dict[str, Any]:
    parse_mod = importlib.import_module("argir.nlp.parse")
    draft, draft_meta = parse_mod.llm_draft(text)
    canon = canonicalize(draft)
    argir = canon.argir

    # STRICT VALIDATION (env or flag)
    strict = (strict if strict is not None else (os.getenv("ARGIR_STRICT","") == "1"))
    validation_issues = []
    if strict:
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
