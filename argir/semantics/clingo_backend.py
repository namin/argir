import re
from typing import Dict, List, Any, Set, Tuple
from . import af_clingo

def parse_apx_text(apx_text: str) -> Tuple[List[str], Set[Tuple[str, str]]]:
    """Parse APX text to extract arguments and attacks."""
    args = []
    atts = []
    arg_set = set()

    for line in apx_text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith('%'):
            continue

        # Parse arg(X).
        if line.startswith('arg(') and line.endswith(').'):
            arg = line[4:-2].strip()
            if arg not in arg_set:
                args.append(arg)
                arg_set.add(arg)

        # Parse att(X,Y).
        elif line.startswith('att(') and line.endswith(').'):
            content = line[4:-2].strip()
            parts = content.split(',')
            if len(parts) == 2:
                src, tgt = parts[0].strip(), parts[1].strip()
                atts.append((src, tgt))
                # Ensure both atoms are in arguments
                if src not in arg_set:
                    args.append(src)
                    arg_set.add(src)
                if tgt not in arg_set:
                    args.append(tgt)
                    arg_set.add(tgt)

    return args, set(atts)

def solve_apx(apx_text: str, semantics: str = 'preferred') -> Dict[str, Any]:
    """Solve APX using af_clingo module."""
    try:
        # Parse APX text
        arguments, attacks = parse_apx_text(apx_text)

        # Map semantics names
        sem_map = {
            'preferred': 'preferred',
            'grounded': 'grounded',
            'stable': 'stable',
            'complete': 'complete',
            'admissible': 'admissible',
            'stage': 'stage',
            'semi-stable': 'semi_stable',
            'semistable': 'semi_stable'
        }

        sem_func = sem_map.get(semantics, 'preferred')

        # Call appropriate function from af_clingo
        if sem_func == 'grounded':
            result = af_clingo.grounded(arguments, attacks)
            # grounded returns a single frozenset
            return {
                'semantics': semantics,
                'in': sorted(list(result)),
                'extensions': [sorted(list(result))]
            }
        elif sem_func == 'preferred':
            result = af_clingo.preferred(arguments, attacks)
        elif sem_func == 'stable':
            result = af_clingo.stable(arguments, attacks)
        elif sem_func == 'complete':
            result = af_clingo.complete(arguments, attacks)
        elif sem_func == 'admissible':
            result = af_clingo.admissible(arguments, attacks)
        elif sem_func == 'stage':
            result = af_clingo.stage(arguments, attacks)
        elif sem_func == 'semi_stable':
            result = af_clingo.semi_stable(arguments, attacks)
        else:
            # Default to preferred
            result = af_clingo.preferred(arguments, attacks)

        # Convert frozensets to sorted lists
        extensions = [sorted(list(ext)) for ext in result]

        return {
            'semantics': semantics,
            'extensions': extensions,
            'in': extensions[0] if extensions else []  # Default to first extension
        }

    except Exception as e:
        return {'semantics': semantics, 'error': str(e), 'apx': apx_text}
