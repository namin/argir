from __future__ import annotations
import shutil, subprocess, tempfile, os
from typing import List, Dict, Any
def call_eprover(fof_lines: List[str], *, time_limit: int=3) -> Dict[str, Any]:
    e = shutil.which("eprover")
    if not e:
        return {"tool":"eprover","available":False,"unsat":False,"sat":False,"note":"eprover not found","raw":""}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "input.p")
        with open(path, "w") as f: f.write("\n".join(fof_lines)+"\n")
        try:
            out = subprocess.run([e, "--auto", "--tstp-format", path], capture_output=True, timeout=time_limit)
        except subprocess.TimeoutExpired:
            return {"tool":"eprover","available":True,"unsat":False,"sat":False,"note":"timeout","raw":""}
    # Decode output with error handling for non-UTF-8 characters
    try:
        txt = (out.stdout or out.stderr).decode('utf-8')
    except UnicodeDecodeError:
        # Fall back to latin-1 which accepts all byte values, or use error handling
        txt = (out.stdout or out.stderr).decode('utf-8', errors='replace')
    # Check for theorem proving status (conjecture proved)
    theorem_proved = "SZS status Theorem" in txt
    # Check for satisfiability/unsatisfiability
    unsat = "SZS status Unsatisfiable" in txt or theorem_proved
    sat = "SZS status Satisfiable" in txt

    result = {"tool":"eprover","available":True,"unsat":unsat,"sat":sat,"raw":txt}
    if theorem_proved:
        result["theorem"] = True
        result["note"] = "Conjecture proved"
    return result
