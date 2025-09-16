from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any, Tuple
from pydantic import BaseModel, Field

class Issue(BaseModel):
    id: str
    type: Literal[
        "unsupported_inference",
        "circular_support",
        "contradiction_unresolved",
        "weak_scheme_instantiation",
        "goal_unreachable"
    ]
    target_node_ids: List[str]
    evidence: Dict[str, Any]
    detector_name: str
    suggested_repairs: List["Repair"] = Field(default_factory=list)
    notes: Optional[str] = None

class Patch(BaseModel):
    add_nodes: List[Dict[str, Any]] = Field(default_factory=list)
    add_edges: List[Dict[str, Any]] = Field(default_factory=list)
    del_edges: List[Dict[str, Any]] = Field(default_factory=list)
    fol_hypotheses: List[str] = Field(default_factory=list)
    af_edits: List[Tuple[str, str, str]] = Field(default_factory=list)

class Verification(BaseModel):
    af_semantics: Literal["grounded", "preferred", "stable"]
    af_goal_accepted: bool
    af_optimal: bool = False
    fol_entailed: Optional[bool] = None
    artifacts: Dict[str, Any] = Field(default_factory=dict)

class Repair(BaseModel):
    id: str
    issue_id: str
    kind: Literal["AF", "FOL"]
    patch: Patch
    cost: int
    verification: Verification