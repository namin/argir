
from __future__ import annotations
import os, json
from typing import Tuple, Dict, Any, Optional

def _load_text(base: str, case_id: str) -> str:
    with open(os.path.join(base, "tests", "nl", case_id + ".txt"), "r", encoding="utf-8") as f:
        return f.read()

def _load_fixture(base: str, case_id: str) -> Dict[str, Any]:
    with open(os.path.join(base, "tests", "fixtures", case_id + ".json"), "r", encoding="utf-8") as f:
        return json.load(f)

def run_case(case_id: str, *, base_dir: Optional[str]=None, fol_mode: str="classical", goal_id: Optional[str]=None, use_fixture: Optional[bool]=None):
    """Run one case through argir.pipeline.run_pipeline.
    If use_fixture is True (or ARGIR_TEST_MODE=fixtures), monkeypatches argir.nlp.parse.llm_draft to return the fixture.
    Returns result dict.
    """
    base = base_dir or os.getcwd()
    text = _load_text(base, case_id)
    use_fix = use_fixture if use_fixture is not None else (os.getenv("ARGIR_TEST_MODE","").lower()=="fixtures")
    import importlib
    from argir.pipeline import run_pipeline
    if use_fix:
        # Monkeypatch llm_draft
        parse_mod = importlib.import_module("argir.nlp.parse")
        def _fake_llm_draft(_text: str):
            # Always load the fixture for the requested case_id
            doc = _load_fixture(base, case_id)
            return doc, {"raw": doc}
        setattr(parse_mod, "llm_draft", _fake_llm_draft)
    return run_pipeline(text, fol_mode=fol_mode, goal_id=goal_id)
