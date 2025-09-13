
import os, unittest, json, re
from typing import List, Dict, Any
from harness import run_case

def _has_goal(fof_lines: List[str], pred: str) -> bool:
    for ln in fof_lines:
        if ln.strip().startswith("fof(goal,") and pred in ln:
            return True
    return False

def _has_axiom(fof_lines: List[str], pattern: str) -> bool:
    return any(pattern in x for x in fof_lines)

class TestARGIR(unittest.TestCase):
    def test_mp_with_undercut_classical(self):
        res = run_case("mp_with_undercut", use_fixture=True)
        # Atoms should be canonical and present
        argir = res["argir"]
        preds = list(argir["metadata"]["atom_lexicon"].keys())
        self.assertIn("raining", preds)
        self.assertIn("streets_get_wet", preds)
        # No coherence gaps expected
        self.assertFalse(any(f["kind"]=="derivability_gap" for f in res["findings"]))
        # FOL should include rule axiom and linkage
        self.assertTrue(_has_axiom(res["fof"], "raining => streets_get_wet"))
        self.assertTrue(_has_axiom(res["fof"], "((raining => streets_get_wet) & raining) => streets_get_wet"))
        # Auto-goal should be conclusion_1 (inference node) and be streets_get_wet
        self.assertTrue(_has_goal(res["fof"], "streets_get_wet"))

    def test_negation_fact_formula(self):
        res = run_case("negation_fact", use_fixture=True)
        fof = "\n".join(res["fof"])
        # Expect negations to show up in TPTP (~(pred))
        self.assertIn("~(raining)", fof)
        self.assertIn("~(streets_get_wet)", fof)

    def test_defeasible_rule_mode(self):
        # Classical: no ~exception in antecedents
        resC = run_case("defeasible_rule", use_fixture=True, fol_mode="classical")
        self.assertTrue(_has_axiom(resC["fof"], "raining => streets_get_wet"))
        self.assertFalse("~(drains_prevent_wet_streets)" in "\n".join(resC["fof"]))
        # Defeasible: (~exception) in antecedents
        resD = run_case("defeasible_rule", use_fixture=True, fol_mode="defeasible")
        self.assertTrue("~(drains_prevent_wet_streets)" in "\n".join(resD["fof"]))

    def test_multi_conclusions_goal_override(self):
        # Auto-selection sees two inference conclusions, so no goal
        res = run_case("multi_conclusions", use_fixture=True)
        self.assertFalse(any(x.startswith("fof(goal,") for x in res["fof"]))
        # With override:
        res2 = run_case("multi_conclusions", use_fixture=True, goal_id="c_street")
        self.assertTrue(_has_goal(res2["fof"], "streets_get_wet"))

    def test_support_cycle_detection(self):
        res = run_case("support_cycle", use_fixture=True)
        # Our simple cycle check only marks support cycles
        cycles = [f for f in res["findings"] if f["kind"]=="circular_support"]
        self.assertTrue(len(cycles) >= 1)

    def test_mutual_attack_apx(self):
        res = run_case("mutual_attack", use_fixture=True)
        apx = json.loads(json.dumps(res["semantics"]))["preferred"]["apx"]
        self.assertIn("att(A,notA).", apx)
        self.assertIn("att(notA,A).", apx)

    def test_lexicon_missing_raises(self):
        # Should raise due to strict enforcement
        with self.assertRaises(Exception):
            run_case("lexicon_missing", use_fixture=True)

    def test_lexicon_mismatch_raises(self):
        with self.assertRaises(Exception):
            run_case("lexicon_mismatch", use_fixture=True)

if __name__ == "__main__":
    unittest.main()
