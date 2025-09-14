from __future__ import annotations
from typing import Dict, Any
from .af import af_projection, to_apx, to_apx_for_clingo
from .clingo_backend import solve_apx
from ..core.model import ARGIR

def compute_extensions(argir: ARGIR) -> Dict[str, Any]:
    """Compute argumentation framework extensions using clingo."""
    args, att = af_projection(argir)

    # Generate APX for clingo (with proper quoting for ASP)
    apx_for_solver = to_apx_for_clingo(args, att)

    # Compute extensions for each semantics
    results = {
        "preferred": solve_apx(apx_for_solver, "preferred"),
        "grounded": solve_apx(apx_for_solver, "grounded"),
        "stable": solve_apx(apx_for_solver, "stable")
    }

    # Include human-readable APX in results for debugging/testing
    readable_apx = to_apx(args, att)
    for sem in results:
        results[sem]["apx"] = readable_apx

    return results
