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

        # Check if we've seen this exact form before
        if norm in self.alias:
            canon = self.alias[norm]
            # Track the surface form as an example
            if surface_pred != canon and surface_pred not in self.entries[canon].examples:
                self.entries[canon].examples.append(surface_pred)
            return canon, []

        # New canonical form - just use the normalized version
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