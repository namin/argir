# argir/canonicalize.py
from __future__ import annotations
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

def _normalize_surface(s: str) -> str:
    """Deterministic, idempotent: lower, strip auxiliaries/dets, collapse -> underscores"""
    s = s.strip().lower()
    for drop in ("it is ", "there is ", "there are ", "is ", "are ", "was ", "were ",
                 "the ", "a ", "an "):
        if s.startswith(drop):
            s = s[len(drop):]
    s = s.replace("'", "")
    s = " ".join(s.split())         # collapse spaces
    return s.replace(" ", "_")

@dataclass
class AtomEntry:
    canonical: str                 # canonical predicate key
    arity: int
    examples: List[str] = field(default_factory=list)

@dataclass
class AtomTable:
    """Project-scoped atom table with stable canonical forms."""
    # pred_key -> AtomEntry
    entries: Dict[str, AtomEntry] = field(default_factory=dict)
    # simple aliasing map (surface -> canonical)
    alias: Dict[str, str] = field(default_factory=dict)

    def propose(self, surface_pred: str, observed_arity: int) -> str:
        norm = _normalize_surface(surface_pred)
        # Do we already have an exact alias?
        if norm in self.alias:
            return self.alias[norm]
        # Try to find near-duplicates by similarity
        best_key, best_sim = None, 0.0
        for key in self.entries:
            sim = SequenceMatcher(None, norm, key).ratio()
            if sim > best_sim:
                best_key, best_sim = key, sim
        if best_key and best_sim >= 0.92 and self.entries[best_key].arity == observed_arity:
            self.alias[norm] = best_key
            self.entries[best_key].examples.append(surface_pred)
            return best_key
        # New canonical
        canon = norm
        # If a clash with different arity exists, disambiguate canon by suffix
        if canon in self.entries and self.entries[canon].arity != observed_arity:
            canon = f"{canon}_{observed_arity}"
        if canon not in self.entries:
            self.entries[canon] = AtomEntry(canonical=canon, arity=observed_arity,
                                            examples=[surface_pred])
        self.alias[norm] = canon
        return canon

    def ensure(self, canonical: str, arity: int):
        if canonical not in self.entries:
            self.entries[canonical] = AtomEntry(canonical=canonical, arity=arity)

    def to_lexicon(self) -> Dict[str, List[str]]:
        """ARGIR metadata.atom_lexicon payload: canonical -> example surface forms."""
        return {k: (v.examples or [k]) for k, v in self.entries.items()}