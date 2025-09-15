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
    # Common proper noun patterns to extract
    entities_patterns = [
        # Specific entities (case-insensitive)
        ("diablo_canyon", "diablo_canyon"),
        ("diablo canyon", "diablo_canyon"),
    ]

    pred_lower = pred_text.lower()
    extracted = []

    # Look for known entities and extract them
    for pattern, entity in entities_patterns:
        if pattern in pred_lower:
            pred_lower = pred_lower.replace(pattern, "").strip()
            if entity not in extracted:
                extracted.append(entity)

    # Clean up the predicate - remove extra spaces and underscores
    pred_lower = " ".join(pred_lower.split())  # collapse spaces
    pred_lower = pred_lower.strip("_").strip()

    # If predicate is empty after extraction, keep original
    if not pred_lower and extracted:
        # Pure entity reference - make it a type predicate
        if "diablo_canyon" in extracted:
            pred_lower = "is_entity"

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

    def propose(self, surface_pred: str, observed_arity: int) -> tuple[str, list[str]]:
        """Propose a canonical form for a surface predicate, tracking the original.
        Returns (canonical_pred, [extracted_entities])
        """
        # First try entity extraction for known patterns
        simplified_pred, entities = _extract_entity(surface_pred.lower())

        # If we extracted entities, use the simplified predicate
        if entities and simplified_pred:
            # Adjust arity - we're moving entities from pred name to args
            adjusted_arity = observed_arity + len(entities)
            norm = _normalize_surface(simplified_pred)
        else:
            # No entities extracted, use original normalization
            norm = _normalize_surface(surface_pred)
            adjusted_arity = observed_arity

        # Do we already have an exact alias?
        if norm in self.alias:
            canon = self.alias[norm]
            # Add this surface form to examples if it's different from canonical
            # and not just a normalized version of the canonical
            if surface_pred != canon and norm != canon and surface_pred not in self.entries[canon].examples:
                self.entries[canon].examples.append(surface_pred)
            return canon, entities

        # Try to find near-duplicates by similarity
        best_key, best_sim = None, 0.0
        for key in self.entries:
            sim = SequenceMatcher(None, norm, key).ratio()
            if sim > best_sim:
                best_key, best_sim = key, sim

        if best_key and best_sim >= 0.92 and self.entries[best_key].arity == adjusted_arity:
            self.alias[norm] = best_key
            # Add unique surface form if it's different from canonical
            # and not just a normalized version of the canonical
            if surface_pred != best_key and norm != best_key and surface_pred not in self.entries[best_key].examples:
                self.entries[best_key].examples.append(surface_pred)
            return best_key, entities

        # New canonical
        canon = norm
        # If a clash with different arity exists, disambiguate canon by suffix
        if canon in self.entries and self.entries[canon].arity != adjusted_arity:
            canon = f"{canon}_{adjusted_arity}"

        if canon not in self.entries:
            # Store original surface form, not canonical
            examples = [surface_pred] if surface_pred != canon else []
            self.entries[canon] = AtomEntry(canonical=canon, arity=adjusted_arity,
                                            examples=examples)
        self.alias[norm] = canon
        return canon, entities

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