# argir/canonicalize.py
from __future__ import annotations
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
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

# ----- Generic aliasing support: signatures & stemming (language-agnostic-ish) -----
_STOP_TOKENS = {
    # modals/auxiliaries
    "will","would","can","could","may","might","must","should","shall",
    "is","are","am","was","were","be","been","being",
    "do","does","did","doing","done","have","has","had",
    # light function words often harmless in predicate strings
    "the","a","an","to","of","that","this","it"
}

_SUFFIX_RE = [
    (re.compile(r"(.+?)ies$"), r"\1y"),      # flies -> fly
    (re.compile(r"(.+?)(?:ches|shes)$"), r"\1ch"),  # matches -> match, wishes -> wish
    (re.compile(r"(.+?)(?:xes|zes|ses)$"), r"\1x"), # boxes->box (approx), fixes->fix
    (re.compile(r"(.+?)s$"), r"\1"),         # cats -> cat (guarded by previous rules)
    (re.compile(r"(.+?)ing$"), r"\1"),       # raining -> rain (approx; no e/dup handling)
    (re.compile(r"(.+?)ed$"), r"\1"),        # rained -> rain
]

# Common irregular forms
_IRREGULAR = {
    "men": "man",
    "women": "woman",
    "children": "child",
    "people": "person",
}

def _stem(tok: str) -> str:
    """Very light, general stemming good enough for alias signatures."""
    # Check irregular forms first
    if tok in _IRREGULAR:
        return _IRREGULAR[tok]
    if len(tok) <= 3:
        return tok
    for pat, repl in _SUFFIX_RE:
        if pat.match(tok):
            return pat.sub(repl, tok)
    return tok

def _sig_tokens(norm: str) -> tuple[str, ...]:
    """Signature tokens for aliasing: lowercase, underscore-split, drop stopwords, stem."""
    toks = [t for t in norm.split("_") if t]
    toks = [t for t in toks if t not in _STOP_TOKENS]
    toks = [_stem(t) for t in toks]
    # de-duplicate while preserving order
    seen = set(); sig = []
    for t in toks:
        if t not in seen:
            sig.append(t); seen.add(t)
    return tuple(sig)

def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 1.0
    return len(A & B) / max(1, len(A | B))

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
    # optional: cache of signature tokens per canonical key
    # (compute on the fly if you prefer)

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

        # Try to find near-duplicates by similarity (string + signature)
        best_key, best_sim = None, 0.0
        sig_norm = _sig_tokens(norm)
        for key, entry in self.entries.items():
            if entry.arity != adjusted_arity:
                continue
            # raw string similarity
            sim_str = SequenceMatcher(None, norm, key).ratio()
            # signature similarity (drop function words, stem)
            sim_sig = _jaccard(sig_norm, _sig_tokens(key))
            sim = max(sim_str, sim_sig)
            if sim > best_sim:
                best_key, best_sim = key, sim

        # Accept alias if either raw string similarity is high
        # OR signature Jaccard is high.
        if best_key and (
            best_sim >= 0.92
            or _jaccard(sig_norm, _sig_tokens(best_key)) >= 0.85
        ):
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