# argir/canonicalize.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import spacy
from functools import lru_cache

def _normalize_surface(s: str) -> str:
    """Simple normalization: lowercase, collapse spaces, replace with underscores.
    The LLM repairs handle all the semantic unification now."""
    s = s.strip().lower()
    s = s.replace("'", "")
    s = " ".join(s.split())  # collapse spaces
    return s.replace(" ", "_")


@lru_cache(maxsize=1)
def _get_nlp():
    """Lazy load spaCy model - using small English model for efficiency.
    Falls back to rule-based if spaCy not available.
    """
    try:
        # Try to load the small English model
        nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
    except OSError:
        try:
            # If not installed, try downloading it
            import subprocess
            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"],
                         capture_output=True, check=False)
            nlp = spacy.load("en_core_web_sm", disable=["parser", "ner"])
        except:
            # Fall back to blank model if download fails
            nlp = spacy.blank("en")
    return nlp

def _lemmatize_predicate(pred: str) -> str:
    """Lemmatize a predicate to its base form using spaCy.

    Handles compound predicates with underscores by lemmatizing parts.
    """
    # Handle underscored compounds
    if "_" in pred:
        parts = pred.split("_")
        # Remove auxiliary verb prefixes
        aux_verbs = {"is", "was", "are", "were", "being", "been", "be",
                    "has", "have", "had", "gets", "get", "got",
                    "become", "becomes", "became", "do", "does", "did"}

        # Filter out auxiliary verbs from the beginning
        original_parts = parts.copy()
        while parts and parts[0] in aux_verbs:
            parts.pop(0)

        if not parts:
            return pred  # Shouldn't happen, but be safe

        # If the remaining part is a gerund and we removed aux verbs, keep the gerund
        if len(parts) == 1 and parts[0].endswith("ing") and len(original_parts) > len(parts):
            # e.g., "is_raining" -> "raining"
            return parts[0]

        # Lemmatize remaining parts
        nlp = _get_nlp()
        lemmatized = []
        for part in parts:
            doc = nlp(part)
            if doc:
                lemmatized.append(doc[0].lemma_ if doc[0].lemma_ != "-PRON-" else part)
            else:
                lemmatized.append(part)

        return "_".join(lemmatized)

    # Simple predicate - use spaCy
    nlp = _get_nlp()
    doc = nlp(pred)
    if doc:
        lemma = doc[0].lemma_
        # spaCy returns "-PRON-" for pronouns, keep original in that case
        if lemma == "-PRON-":
            return pred
        # For gerunds, keep them as-is (states/activities)
        if pred.endswith("ing") and lemma != pred:
            # But do lemmatize if it's a auxiliary + verb pattern
            return pred  # Keep gerund form for states
        return lemma
    return pred

# Domain-specific synonyms - minimal set for logical operators
# Let the LLM repairs handle most semantic unification
SYNONYM_MAP = {
    # Logical relations
    "entail": "imply",
    "therefore": "imply",
    # Keep attack/contradict distinct from each other
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

        # Apply lemmatization for morphological normalization
        norm = _lemmatize_predicate(norm)

        # Apply domain-specific synonyms (minimal)
        if norm in SYNONYM_MAP:
            norm = SYNONYM_MAP[norm]

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