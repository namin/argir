from __future__ import annotations
from typing import List, Optional, Literal, Dict, Union
from pydantic import BaseModel, Field

class TextSpan(BaseModel):
    start: int
    end: int
    text: Optional[str] = None

class Term(BaseModel):
    kind: Literal["Var","Const"] = "Const"
    name: str

class Atom(BaseModel):
    pred: str
    args: List[Term] = Field(default_factory=list)
    negated: bool = False

class Quantifier(BaseModel):
    kind: Literal["forall","exists"]
    var: str
    sort: Optional[str] = None

class Statement(BaseModel):
    kind: Literal["Stmt"] = "Stmt"
    text: str
    atoms: List[Atom] = Field(default_factory=list)
    quantifiers: List[Quantifier] = Field(default_factory=list)
    span: Optional[TextSpan] = None
    rationale: Optional[str] = None
    confidence: Optional[float] = None

class NodeRef(BaseModel):
    kind: Literal["Ref"] = "Ref"
    ref: str
    note: Optional[str] = None

Premise = Union[Statement, NodeRef]

class Rule(BaseModel):
    name: str = "r"
    strict: bool = False
    antecedents: List[Statement] = Field(default_factory=list)
    consequents: List[Statement] = Field(default_factory=list)
    exceptions: List[Statement] = Field(default_factory=list)
    span: Optional[TextSpan] = None
    scheme: Optional[str] = None
    rationale: Optional[str] = None

class InferenceStep(BaseModel):
    id: str
    premises: List[Premise] = Field(default_factory=list)
    rule: Optional[Rule] = None
    conclusion: Optional[Statement] = None
    span: Optional[TextSpan] = None
    rationale: Optional[str] = None

EdgeType = Literal["support","attack"]
AttackKind = Literal["rebut","undermine","undercut","unknown"]

class Edge(BaseModel):
    source: str
    target: str
    kind: EdgeType
    attack_kind: Optional[AttackKind] = None
    rationale: Optional[str] = None

class ArgumentGraph(BaseModel):
    nodes: List[InferenceStep] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)

class ARGIR(BaseModel):
    version: str = "0.3.3"
    source_text: str
    spans_indexed: bool = True
    graph: ArgumentGraph
    metadata: Dict[str, object] = Field(default_factory=dict)
