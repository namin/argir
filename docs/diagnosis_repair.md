# ARGIR Diagnosis & Repair System

## Overview

The ARGIR Diagnosis & Repair (D&R) system detects logical issues in argument structures and proposes minimal, verified repairs. It combines:

- **Issue Detection**: Identifies problems like unsupported inferences, circular reasoning, contradictions, weak argumentation schemes, and unreachable goals
- **Automated Repair**: Generates minimal fixes using Answer Set Programming (ASP) for argumentation framework repairs and abductive reasoning for missing premises
- **Verification**: Validates repairs using Clingo (AF semantics) and E-prover (FOL entailment)

## Installation

Requirements:
- Python 3.8+
- Clingo (for AF semantics and repair)
- E-prover (optional, for FOL verification)
- NetworkX (for graph analysis)

```bash
pip install networkx
# Install clingo: conda install -c potassco clingo
# Install E-prover: https://eprover.github.io/
```

## Usage

### Basic Diagnosis

Detect issues in an argument:

```bash
python -m argir.cli input.txt --out output_dir --soft --diagnose
```

### Diagnosis with Repair

Generate and verify repairs:

```bash
python -m argir.cli input.txt --out output_dir --soft --diagnose --repair
```

### Options

- `--diagnose`: Enable issue detection
- `--repair`: Generate repairs for detected issues
- `--semantics {grounded,preferred,stable}`: AF semantics (default: grounded)
- `--max-af-edits N`: Maximum AF edge edits for repair (default: 2)
- `--max-abduce N`: Maximum atoms for abduction (default: 2)
- `--eprover-path PATH`: Path to E-prover executable
- `--goal NODE_ID`: Specify goal node for analysis

## Issue Types

### 1. Unsupported Inference
- **Detection**: Inference node lacks premises or premises don't entail conclusion
- **Repair**: Abduce missing premises or add support edges

### 2. Circular Support
- **Detection**: Cycle in derivation graph where conclusion depends on itself
- **Repair**: Add independent support or break cycle

### 3. Contradiction Unresolved
- **Detection**: Nodes with opposite polarity atoms or mutual attacks
- **Repair**: Remove conflicting attacks or add defenders

### 4. Weak Scheme Instantiation
- **Detection**: Argumentation scheme missing critical backing/evidence
- **Repair**: Add backing premises or qualifiers

### 5. Goal Unreachable
- **Detection**: Goal not accepted under target semantics
- **Repair**: Minimal AF edits to make goal accepted

## Output Files

The system generates:
- `report.md`: Enhanced report with issue cards and repairs
- `issues.json`: Detected issues in machine-readable format
- `repairs.json`: Generated repairs with verification results

## Example: Issue Card

```markdown
### Issue I-001: Unsupported Inference (C1)
**Why:** Premises do not entail the conclusion

**Minimal repair (verified):**
- Add premise: raining()
- Add support: P_new → C1

**Verification:**
- AF (grounded): goal accepted ✅
- FOL (E-prover): entailed ✅

**Patch (machine-readable):**
{
  "add_nodes": [{"id":"P_new","atoms":[{"pred":"raining"}]}],
  "add_edges": [{"source":"P_new","target":"C1","kind":"support"}],
  "fol_hypotheses": ["raining"]
}
```

## Programmatic API

```python
from argir.diagnostics import diagnose
from argir.repairs.af_enforce import enforce_goal
from argir.repairs.fol_abduction import abduce_missing_premises

# Run diagnosis
issues = diagnose(argir_dict, goal_id="C1", semantics="grounded")

# Generate repairs
for issue in issues:
    if issue.type == "goal_unreachable":
        repairs = enforce_goal(argir_dict, issue, semantics="grounded")
    elif issue.type == "unsupported_inference":
        repairs = abduce_missing_premises(argir_dict, issue, max_atoms=2)
```

## Architecture

```
NL text → ARGIR extraction → Diagnosis → Repair Generation → Verification
                                ↓              ↓                   ↓
                            Issues list    AF/FOL patches    Success metrics
```

### Key Components

1. **diagnostics.py**: Issue detection algorithms
2. **repairs/af_enforce.py**: ASP-based AF repair with minimization
3. **repairs/fol_abduction.py**: Hypothesis search for missing premises
4. **reporting.py**: Issue card generation for reports
5. **types.py**: Data models for issues, repairs, and verification

## Testing

Run the test suite:

```bash
python -m unittest tests.test_diagnosis -v
```

Test cases cover:
- Unsupported inference detection
- Circular reasoning detection
- Contradiction detection
- AF repair generation
- FOL abduction
- Integration with full pipeline

## Limitations

- Repairs are minimal w.r.t. the candidate pool, not globally optimal
- FOL abduction limited to 2 atoms from the lexicon
- E-prover required for FOL verification (fallback to AF-only)
- Scheme detection uses simple heuristics

## References

- ASPARTIX encodings for Dung AF semantics
- Enforcement in formal argumentation (Baumann & Brewka)
- ARGIR core system (github.com/namin/argir)