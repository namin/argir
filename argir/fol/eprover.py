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
            out = subprocess.run([e, "--auto", "--tstp-format", path], capture_output=True, text=True, timeout=time_limit)
        except subprocess.TimeoutExpired:
            return {"tool":"eprover","available":True,"unsat":False,"sat":False,"note":"timeout","raw":""}
    txt = out.stdout or out.stderr
    return {"tool":"eprover","available":True,"unsat":"SZS status Unsatisfiable" in txt,"sat":"SZS status Satisfiable" in txt,"raw":txt}
