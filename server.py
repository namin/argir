#!/usr/bin/env python3
"""FastAPI server for ARGIR - Argument Graph Intermediate Representation"""
from __future__ import annotations

import os
from typing import Optional
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from argir.pipeline import run_pipeline, run_pipeline_soft
from argir.nlp.llm import set_request_api_key
from argir.diagnostics import diagnose
from argir.repairs.af_enforce import enforce_goal
from argir.repairs.fol_abduction import abduce_missing_premises
from argir.reporting import render_diagnosis_report
import argir as _argir_pkg

app = FastAPI(title="ARGIR API", version=_argir_pkg.__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ArgirRequest(BaseModel):
    text: str
    fol_mode: str = "classical"  # "classical" or "defeasible"
    goal_id: Optional[str] = None
    use_soft: bool = False
    k_samples: int = 1
    api_key: Optional[str] = None  # For Gemini API key
    enable_diagnosis: bool = False  # Enable issue detection
    enable_repair: bool = False  # Enable repair generation
    semantics: str = "grounded"  # AF semantics for diagnosis
    max_af_edits: int = 2  # Maximum AF edits for repair
    max_abduce: int = 2  # Maximum atoms for abduction

@app.get("/api/health")
def health():
    """Health check endpoint"""
    return {
        "ok": True,
        "version": _argir_pkg.__version__,
        "package_path": _argir_pkg.__file__
    }

@app.post("/api/analyze")
def analyze_arguments(req: ArgirRequest, x_api_key: Optional[str] = Header(None)):
    """Main endpoint for analyzing natural language arguments"""
    # Set the request-scoped API key (prefer header, fallback to body)
    api_key = x_api_key or req.api_key
    if api_key:
        set_request_api_key(api_key)

    try:
        if not req.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")

        # Run the appropriate pipeline
        if req.use_soft:
            result = run_pipeline_soft(
                req.text,
                fol_mode=req.fol_mode,
                goal_id=req.goal_id,
                k_samples=req.k_samples
            )
        else:
            result = run_pipeline(
                req.text,
                fol_mode=req.fol_mode,
                goal_id=req.goal_id
            )

        # Run diagnosis if requested
        issues = []
        repairs = []

        if req.enable_diagnosis or req.enable_repair:
            try:
                # Run diagnosis
                issues = diagnose(
                    result["argir"],
                    goal_id=req.goal_id,
                    semantics=req.semantics
                )

                # Generate repairs if requested
                if req.enable_repair and issues:
                    for issue in issues:
                        if issue.type in ["goal_unreachable", "contradiction_unresolved"]:
                            issue_repairs = enforce_goal(
                                result["argir"],
                                issue,
                                semantics=req.semantics,
                                max_edits=req.max_af_edits
                            )
                            repairs.extend(issue_repairs)

                        if issue.type in ["unsupported_inference", "weak_scheme_instantiation"]:
                            issue_repairs = abduce_missing_premises(
                                result["argir"],
                                issue,
                                max_atoms=req.max_abduce
                            )
                            repairs.extend(issue_repairs)
            except Exception as e:
                # Log but don't fail the entire request
                import traceback
                print(f"Diagnosis/repair error: {e}")
                traceback.print_exc()

        # Update the report with diagnosis results
        if issues or repairs:
            result["report_md"] = render_diagnosis_report(issues, repairs, result.get("report_md", ""))

        # Include validation warnings if present
        response = {
            "success": True,
            "result": result,
            "issues": [issue.model_dump() for issue in issues] if issues else [],
            "repairs": [repair.model_dump() for repair in repairs] if repairs else []
        }

        # Handle validation issues
        if req.use_soft and result.get('soft_validation'):
            validation_report = result['soft_validation']
            warnings = []
            errors = []

            if hasattr(validation_report, 'errors') and validation_report.errors():
                for issue in validation_report.errors():
                    errors.append({
                        "code": issue.code,
                        "path": issue.path,
                        "message": issue.message
                    })

            if hasattr(validation_report, 'warn') and validation_report.warn():
                for issue in validation_report.warn():
                    warnings.append({
                        "code": issue.code,
                        "path": issue.path,
                        "message": issue.message
                    })

            if errors or warnings:
                response["validation"] = {
                    "errors": errors,
                    "warnings": warnings
                }
        elif result.get('validation_issues'):
            response["validation"] = {
                "warnings": result['validation_issues']
            }

        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)