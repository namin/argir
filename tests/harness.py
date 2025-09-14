
from __future__ import annotations
import os, json
from typing import Dict, Any, Optional

# Get the test directory path relative to this file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_text(case_id: str) -> str:
    """Load test input text from nl/ directory."""
    nl_path = os.path.join(TEST_DIR, "nl", f"{case_id}.txt")
    with open(nl_path, "r", encoding="utf-8") as f:
        return f.read()

def _load_fixture(case_id: str) -> Dict[str, Any]:
    """Load fixture JSON from fixtures/ directory."""
    fixture_path = os.path.join(TEST_DIR, "fixtures", f"{case_id}.json")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return json.load(f)

def run_case(case_id: str, *, fol_mode: str="classical", goal_id: Optional[str]=None, use_fixture: Optional[bool]=None):
    """Run one case through argir.pipeline.run_pipeline.
    If use_fixture is True (or ARGIR_TEST_MODE=fixtures), monkeypatches argir.nlp.parse.llm_draft to return the fixture.
    Returns result dict.
    """
    text = _load_text(case_id)
    use_fix = use_fixture if use_fixture is not None else (os.getenv("ARGIR_TEST_MODE","").lower()=="fixtures")
    import importlib
    from argir.pipeline import run_pipeline
    if use_fix:
        # Monkeypatch llm_draft
        parse_mod = importlib.import_module("argir.nlp.parse")
        def _fake_llm_draft(_text: str):
            # Always load the fixture for the requested case_id
            doc = _load_fixture(case_id)
            return doc, {"raw": doc}
        setattr(parse_mod, "llm_draft", _fake_llm_draft)
    return run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id)
