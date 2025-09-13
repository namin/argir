from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Union


@dataclass(frozen=True)
class Var:
    name: str
    sort: Optional[str] = None


@dataclass(frozen=True)
class Const:
    name: str
    sort: Optional[str] = None


Term = Union[Var, Const]


@dataclass(frozen=True)
class Pred:
    name: str
    arity: int


@dataclass(frozen=True)
class Atom:
    pred: Pred
    args: List[Term]
    negated: bool = False


@dataclass(frozen=True)
class Not:
    phi: "Formula"


@dataclass(frozen=True)
class And:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class Or:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class Implies:
    left: "Formula"
    right: "Formula"


@dataclass(frozen=True)
class Forall:
    var: Var
    body: "Formula"


@dataclass(frozen=True)
class Exists:
    var: Var
    body: "Formula"


Formula = Union[Atom, Not, And, Or, Implies, Forall, Exists]
