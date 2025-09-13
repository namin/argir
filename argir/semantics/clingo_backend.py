from typing import Dict
def solve_apx(apx_text: str, semantics: str = 'preferred') -> Dict[str, object]:
    return {'semantics': semantics, 'apx': apx_text}
