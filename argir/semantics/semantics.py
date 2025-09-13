from __future__ import annotations
from typing import Dict, Any
from .af import af_projection, to_apx
from .clingo_backend import solve_apx
from ..core.model import ARGIR
def compute_extensions(argir: ARGIR) -> Dict[str, Any]:
    args, att = af_projection(argir)
    apx = to_apx(args, att)
    return {"preferred": solve_apx(apx, "preferred"),
            "grounded": solve_apx(apx, "grounded"),
            "stable": solve_apx(apx, "stable")}
