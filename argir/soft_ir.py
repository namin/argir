# argir/soft_ir.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Literal, Union, Any

# ---- Soft IR types (easy for LLM to emit) ----

AtomKey = str
NodeId  = str  # provisional IDs allowed (LLM can make up "n1","c3", etc.)

@dataclass
class SoftSpan:
    text: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None

@dataclass
class SoftTerm:
    """Argument term; keep it simple & typeless for now."""
    value: str

@dataclass
class SoftStatement:
    pred: str                 # e.g., "raining", "is wet"
    args: List[SoftTerm]      # e.g., ["Paris"]
    polarity: Literal["pos","neg"] = "pos"
    span: Optional[SoftSpan] = None
    quantifiers: Optional[List[Any]] = None  # Optional quantifiers for goals

@dataclass
class SoftRule:
    name: Optional[str] = None
    strict: bool = False
    antecedents: List[SoftStatement] = field(default_factory=list)
    consequents: List[SoftStatement] = field(default_factory=list)
    exceptions: List[SoftStatement] = field(default_factory=list)

@dataclass
class SoftPremiseRef:
    kind: Literal["Ref"] = "Ref"
    ref: str = ""            # NodeId (LLM provisional is fine)

SoftPremise = Union[SoftStatement, SoftPremiseRef]

@dataclass
class SoftNode:
    id: Optional[NodeId] = None     # optional; compiler will assign stable ids
    premises: List[SoftPremise] = field(default_factory=list)
    rule: Optional[SoftRule] = None
    conclusion: Optional[SoftStatement] = None
    span: Optional[SoftSpan] = None
    rationale: Optional[str] = None

@dataclass
class SoftEdge:
    source: str         # NodeId or provisional ID/label
    target: str
    kind: Literal["support", "attack"]
    attack_kind: Optional[str] = None
    rationale: Optional[str] = None

@dataclass
class SoftGraph:
    nodes: List[SoftNode]
    edges: List[SoftEdge]

@dataclass
class SoftIR:
    version: str
    source_text: str
    graph: SoftGraph
    # LLM can omit canonical lexicon here (we'll build it deterministically)
    metadata: Dict[str, dict] = field(default_factory=dict)
    goal: Optional[Dict[str, str]] = None  # Optional goal specification