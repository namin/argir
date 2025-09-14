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

def _extract_entity(pred_text: str) -> tuple[str, list[str]]:
    """Extract proper nouns and entities from predicate text.
    Returns (simplified_pred, [entities])
    """
    # Common proper nouns to extract (extend as needed)
    entities_patterns = [
        ("diablo_canyon", "diablo_canyon"),
        ("diablo canyon", "diablo_canyon"),
        ("nuclear_power_plant", "nuclear_plant"),
        ("power_plant", "plant"),
    ]

    pred_lower = pred_text.lower()
    extracted = []

    # Look for known entities
    for pattern, entity in entities_patterns:
        if pattern in pred_lower:
            pred_lower = pred_lower.replace(pattern, "")
            extracted.append(entity)

    # Clean up the predicate
    pred_lower = " ".join(pred_lower.split())  # collapse spaces
    pred_lower = pred_lower.strip("_").strip()

    return pred_lower, extracted

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
        """Propose a canonical form for a surface predicate, tracking the original."""
        norm = _normalize_surface(surface_pred)

        # Do we already have an exact alias?
        if norm in self.alias:
            canon = self.alias[norm]
            # Add this surface form to examples if it's different from canonical
            if surface_pred != canon and surface_pred not in self.entries[canon].examples:
                self.entries[canon].examples.append(surface_pred)
            return canon

        # Try to find near-duplicates by similarity
        best_key, best_sim = None, 0.0
        for key in self.entries:
            sim = SequenceMatcher(None, norm, key).ratio()
            if sim > best_sim:
                best_key, best_sim = key, sim

        if best_key and best_sim >= 0.92 and self.entries[best_key].arity == observed_arity:
            self.alias[norm] = best_key
            # Add unique surface form
            if surface_pred not in self.entries[best_key].examples:
                self.entries[best_key].examples.append(surface_pred)
            return best_key

        # New canonical
        canon = norm
        # If a clash with different arity exists, disambiguate canon by suffix
        if canon in self.entries and self.entries[canon].arity != observed_arity:
            canon = f"{canon}_{observed_arity}"

        if canon not in self.entries:
            # Store original surface form, not canonical
            examples = [surface_pred] if surface_pred != canon else []
            self.entries[canon] = AtomEntry(canonical=canon, arity=observed_arity,
                                            examples=examples)
        self.alias[norm] = canon
        return canon

    def ensure(self, canonical: str, arity: int):
        if canonical not in self.entries:
            self.entries[canonical] = AtomEntry(canonical=canonical, arity=arity)

    def to_lexicon(self) -> Dict[str, List[str]]:
        """ARGIR metadata.atom_lexicon payload: canonical -> example surface forms."""
        lexicon = {}
        for k, v in self.entries.items():
            # If we have real surface examples, use them
            if v.examples:
                lexicon[k] = v.examples
            else:
                # Only use canonical as fallback, and mark it
                lexicon[k] = [k]
        return lexicon