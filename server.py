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
from fastapi.responses import PlainTextResponse, HTMLResponse
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

        # Also save the full results for caching
        save_results(saved_hash, response)

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

def save_results(query_hash: str, response: Dict[str, Any]) -> None:
    """Save full analysis results to the saved-results/ directory for caching"""
    results_dir = Path("saved-results")
    results_dir.mkdir(exist_ok=True)

    # Serialize the response (handle Pydantic models)
    def make_serializable(obj):
        if hasattr(obj, 'model_dump'):
            return obj.model_dump()
        elif isinstance(obj, dict):
            return {k: make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [make_serializable(item) for item in obj]
        elif isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        else:
            return str(obj)

    try:
        serializable_response = make_serializable(response)
        file_path = results_dir / f"{query_hash}.json"
        with open(file_path, 'w') as f:
            json.dump(serializable_response, f, indent=2)
    except Exception as e:
        # Don't fail the request if results caching fails
        print(f"Warning: Failed to cache results for {query_hash}: {e}")

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
                    "text": data.get("text", ""),
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

def get_plain_content(data: Dict[str, Any], format_type: str) -> tuple[str, str]:
    """Extract plain content from saved query data based on format type.
    
    Returns (content, content_type) tuple.
    """
    if format_type == "md" or format_type == "markdown":
        # Return the markdown report if available
        if "result" in data and "report_md" in data["result"]:
            return data["result"]["report_md"], "text/markdown"
        else:
            # Fallback: create a simple markdown from available data
            if "text" in data:
                timestamp = data.get("timestamp", "Unknown")
                fol_mode = data.get("fol_mode", "Unknown")
                markdown_content = f"""# ARGIR Query

## Query Text
{data["text"]}

## Parameters
- **FOL Mode**: {fol_mode}
- **Timestamp**: {timestamp}
- **Goal ID**: {data.get("goal_id", "None")}
- **Diagnosis Enabled**: {data.get("enable_diagnosis", False)}
- **Repair Enabled**: {data.get("enable_repair", False)}

*Note: This is a saved query without full analysis results. Run the analysis to get a complete report.*
"""
                return markdown_content, "text/markdown"
            else:
                return "No markdown report available", "text/plain"
    
    elif format_type == "txt" or format_type == "text":
        # Return the source text - handle different data structures
        if "text" in data:
            # Direct text field (from save_query format)
            return data["text"], "text/plain"
        elif "query" in data and "text" in data["query"]:
            # Nested under query (from full analysis format)
            return data["query"]["text"], "text/plain"
        elif "result" in data and "source_text" in data["result"]:
            # Nested under result (from full analysis format)
            return data["result"]["source_text"], "text/plain"
        else:
            return "No text content available", "text/plain"
    
    elif format_type == "html":
        # Convert markdown to basic HTML if available, otherwise show structured data
        if "result" in data and "report_md" in data["result"]:
            # Simple markdown-to-HTML conversion for basic formatting
            html_content = data["result"]["report_md"]
            html_content = html_content.replace("\n# ", "\n<h1>").replace("\n## ", "\n<h2>").replace("\n### ", "\n<h3>")
            html_content = html_content.replace("\n<h1>", "</h1>\n<h1>").replace("\n<h2>", "</h2>\n<h2>").replace("\n<h3>", "</h3>\n<h3>")
            html_content = html_content.replace("```json\n", "<pre><code>").replace("```\n", "</code></pre>\n")
            html_content = html_content.replace("```", "<code>").replace("\n\n", "</p>\n<p>")
            html_content = f"<html><head><title>ARGIR Report</title></head><body><h1>{html_content}</h1></body></html>"
            return html_content, "text/html"
        else:
            # Fallback to basic HTML structure
            query_text = data.get("query", {}).get("text", "No query text")
            html_content = f"""
            <html>
            <head><title>ARGIR Query</title></head>
            <body>
                <h1>ARGIR Analysis</h1>
                <h2>Query Text</h2>
                <p>{query_text}</p>
                <h2>Timestamp</h2>
                <p>{data.get("query", {}).get("timestamp", "Unknown")}</p>
            </body>
            </html>
            """
            return html_content, "text/html"
    
    elif format_type == "json":
        # Return the full JSON data, pretty-printed
        # Handle non-serializable objects
        def make_serializable(obj):
            """Convert non-serializable objects to serializable format"""
            if hasattr(obj, 'model_dump'):
                # Pydantic models
                return obj.model_dump()
            elif hasattr(obj, '__dict__'):
                # Other objects with __dict__
                return {k: make_serializable(v) for k, v in obj.__dict__.items()}
            elif isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_serializable(item) for item in obj]
            elif isinstance(obj, (str, int, float, bool)) or obj is None:
                return obj
            else:
                # Fallback: convert to string
                return str(obj)
        
        try:
            serializable_data = make_serializable(data)
            return json.dumps(serializable_data, indent=2), "application/json"
        except Exception as e:
            # If all else fails, return a simple error structure
            error_data = {
                "error": "JSON serialization failed",
                "message": str(e),
                "data_type": str(type(data))
            }
            return json.dumps(error_data, indent=2), "application/json"
    
    elif format_type == "fol" or format_type == "fof":
        # Return FOL axioms if available
        if "result" in data and "fof" in data["result"]:
            fol_axioms = data["result"]["fof"]
            if isinstance(fol_axioms, list):
                return "\n".join(fol_axioms), "text/plain"
            else:
                return str(fol_axioms), "text/plain"
        else:
            return "No FOL axioms available", "text/plain"
    
    elif format_type == "apx":
        # Return APX format if available
        if "result" in data and "semantics" in data["result"]:
            semantics = data["result"]["semantics"]
            if "grounded" in semantics and "apx" in semantics["grounded"]:
                return semantics["grounded"]["apx"], "text/plain"
            elif "preferred" in semantics and "apx" in semantics["preferred"]:
                return semantics["preferred"]["apx"], "text/plain"
        return "No APX format available", "text/plain"
    
    else:
        # Default to JSON for unknown formats
        return json.dumps(data, indent=2), "application/json"

@app.get("/plain/{query_hash_or_file}")
def get_plain_query_smart(query_hash_or_file: str):
    """Retrieve a saved query in plain format, supporting both hash.ext and hash formats"""
    if '.' in query_hash_or_file:
        # Handle file extension format (e.g., hash.md, hash.txt)
        query_hash, extension = query_hash_or_file.rsplit('.', 1)
        return get_plain_query_format(query_hash, extension)
    else:
        # No extension, default to markdown
        return get_plain_query_format(query_hash_or_file, "md")

@app.get("/plain/{query_hash}/{format_type}")
def get_plain_query_format(query_hash: str, format_type: str):
    """Retrieve a saved query and run analysis, returning results in specified plain format
    
    Supported formats:
    - md/markdown: Markdown report
    - txt/text: Source text only  
    - html: HTML formatted report
    - json: Full JSON data
    - fol/fof: FOL axioms
    - apx: APX format for argument frameworks
    """
    file_path = Path("saved") / f"{query_hash}.json"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Saved query not found")

    # Load the saved query parameters
    with open(file_path) as f:
        query_params = json.load(f)
    
    try:
        # Recreate the ArgirRequest from saved parameters
        req = ArgirRequest(
            text=query_params.get("text", ""),
            fol_mode=query_params.get("fol_mode", "classical"),
            goal_id=query_params.get("goal_id"),
            goal_hint=query_params.get("goal_hint"),
            use_soft=query_params.get("use_soft", False),
            k_samples=query_params.get("k_samples", 1),
            enable_diagnosis=query_params.get("enable_diagnosis", False),
            enable_repair=query_params.get("enable_repair", False),
            semantics=query_params.get("semantics", "grounded"),
            max_af_edits=query_params.get("max_af_edits", 2),
            max_abduce=query_params.get("max_abduce", 2)
        )
        
        # Run the analysis (reusing logic from analyze_arguments)
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
                issues = diagnose(
                    result["argir"],
                    goal_id=req.goal_id,
                    semantics=req.semantics
                )

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
                print(f"Diagnosis/repair error: {e}")

        # Update the report with diagnosis results
        if issues or repairs:
            result["report_md"] = render_diagnosis_report(issues, repairs, result.get("report_md", ""))

        # Create full analysis data structure for get_plain_content
        full_data = {
            "query": query_params,
            "result": result,
            "issues": [issue.model_dump() for issue in issues] if issues else [],
            "repairs": [repair.model_dump() for repair in repairs] if repairs else []
        }
        
        content, content_type = get_plain_content(full_data, format_type.lower())
        
        if content_type == "text/html":
            return HTMLResponse(content=content)
        else:
            return PlainTextResponse(content=content, media_type=content_type)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)