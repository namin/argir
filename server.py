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

        # Include validation warnings if present
        response = {
            "success": True,
            "result": result
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