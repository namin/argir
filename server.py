#!/usr/bin/env python3
"""FastAPI server for ARGIR - Argument Graph Intermediate Representation"""
from __future__ import annotations

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
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
    goal_id: Optional[str] = None  # Explicit goal node ID (like C1, P2)
    goal_hint: Optional[str] = None  # Goal text hint for LLM (like "We should use nuclear energy")
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
                goal_hint=req.goal_hint,
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

        # Save the query if successful
        saved_hash = save_query(req)
        response["saved_hash"] = saved_hash

        return response

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {str(e)}")

def save_query(req: ArgirRequest) -> str:
    """Save a query to the saved/ directory and return its hash"""
    saved_dir = Path("saved")
    saved_dir.mkdir(exist_ok=True)

    # Create query data with timestamp
    query_data = {
        "text": req.text,
        "fol_mode": req.fol_mode,
        "goal_id": req.goal_id,
        "goal_hint": req.goal_hint,
        "use_soft": req.use_soft,
        "k_samples": req.k_samples,
        "enable_diagnosis": req.enable_diagnosis,
        "enable_repair": req.enable_repair,
        "semantics": req.semantics,
        "max_af_edits": req.max_af_edits,
        "max_abduce": req.max_abduce,
        "timestamp": datetime.now().isoformat()
    }

    # Generate hash from the query content (excluding timestamp)
    query_str = json.dumps({k: v for k, v in query_data.items() if k != "timestamp"}, sort_keys=True)
    query_hash = hashlib.sha256(query_str.encode()).hexdigest()[:12]

    # Save to file
    file_path = saved_dir / f"{query_hash}.json"
    with open(file_path, 'w') as f:
        json.dump(query_data, f, indent=2)

    return query_hash

@app.get("/api/saved")
def list_saved_queries() -> List[Dict[str, Any]]:
    """List all saved queries with previews"""
    saved_dir = Path("saved")
    if not saved_dir.exists():
        return []

    queries = []
    for file_path in saved_dir.glob("*.json"):
        try:
            with open(file_path) as f:
                data = json.load(f)
                queries.append({
                    "hash": file_path.stem,
                    "text": data.get("text", "")[:100] + ("..." if len(data.get("text", "")) > 100 else ""),
                    "timestamp": data.get("timestamp"),
                    "fol_mode": data.get("fol_mode"),
                    "goal_id": data.get("goal_id")
                })
        except:
            continue

    # Sort by timestamp (newest first)
    queries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return queries

@app.get("/api/saved/{query_hash}")
def get_saved_query(query_hash: str) -> Dict[str, Any]:
    """Retrieve a specific saved query by hash"""
    file_path = Path("saved") / f"{query_hash}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Saved query not found")

    with open(file_path) as f:
        return json.load(f)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)