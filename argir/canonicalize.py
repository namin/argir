# argir/canonicalize.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

def _normalize_surface(s: str) -> str:
    """Simple normalization: lowercase, collapse spaces, replace with underscores.
    The LLM repairs handle all the semantic unification now."""
    s = s.strip().lower()
    s = s.replace("'", "")
    s = " ".join(s.split())  # collapse spaces
    return s.replace(" ", "_")


# Common morphological variants and synonyms mapping
PREDICATE_CANON_MAP = {
    # Verb forms
    "rain": "raining",
    "rains": "raining",
    "rained": "raining",
    "is_raining": "raining",
    "wet": "wet",
    "is_wet": "wet",
    "gets_wet": "wet",
    "become_wet": "wet",
    # Common logical predicates
    "implies": "implies",
    "entails": "implies",
    "therefore": "implies",
    "supports": "supports",
    "support": "supports",
    "supporting": "supports",
    # Attack predicates
    "attacks": "attacks",
    "attack": "attacks",
    "attacking": "attacks",
    "contradicts": "contradicts",
    "contradict": "contradicts",
}


@dataclass
class AtomEntry:
    canonical: str                 # canonical predicate key
    arity: int
    examples: List[str] = field(default_factory=list)

@dataclass
class AtomTable:
    """Simple atom table that tracks canonical forms.
    LLM repairs handle semantic unification, this just tracks what we've seen."""
    # pred_key -> AtomEntry
    entries: Dict[str, AtomEntry] = field(default_factory=dict)
    # simple aliasing map (surface -> canonical)
    alias: Dict[str, str] = field(default_factory=dict)

    def propose(self, surface_pred: str, observed_arity: int) -> tuple[str, list[str]]:
        """Propose a canonical form for a surface predicate.
        Since LLM repairs handle semantic unification, this just does simple normalization.
        Returns (canonical_pred, []) - empty list for compatibility
        """
        # Simple normalization
        norm = _normalize_surface(surface_pred)

        # Apply morphological canonicalization
        if norm in PREDICATE_CANON_MAP:
            norm = PREDICATE_CANON_MAP[norm]

        # Check if we've seen this exact form before
        if norm in self.alias:
            canon = self.alias[norm]
            # Track the surface form as an example
            if surface_pred != canon and surface_pred not in self.entries[canon].examples:
                self.entries[canon].examples.append(surface_pred)
            return canon, []

        # New canonical form - use the canonicalized version
        canon = norm

        # If there's an arity clash, disambiguate
        if canon in self.entries and self.entries[canon].arity != observed_arity:
            canon = f"{canon}_{observed_arity}"

        if canon not in self.entries:
            # Store original surface form as example
            examples = [surface_pred] if surface_pred != canon else []
            self.entries[canon] = AtomEntry(canonical=canon, arity=observed_arity,
                                            examples=examples)
        self.alias[norm] = canon
        return canon, []

    def ensure(self, canonical: str, arity: int):
        if canonical not in self.entries:
            self.entries[canonical] = AtomEntry(canonical=canonical, arity=arity)

    def to_lexicon(self) -> Dict[str, any]:
        """ARGIR metadata.atom_lexicon payload with predicates and constants."""
        # Format expected by abduction module:
        # {"predicates": {pred: arity}, "constants": [list]}
        predicates = {}
        constants = set()

        for k, v in self.entries.items():
            predicates[k] = v.arity
            # Extract constants from examples (simplified)
            for ex in v.examples:
                # Basic extraction - could be enhanced
                pass

        return {
            "predicates": predicates,
            "constants": sorted(list(constants)),
            "surface_forms": {k: v.examples if v.examples else [k]
                            for k, v in self.entries.items()}
        }