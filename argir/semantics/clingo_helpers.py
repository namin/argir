"""
Common helper functions for working with Clingo/ASP.
"""
from typing import List, Tuple


def quote_id(id_str: str) -> str:
    """
    Quote an ID if needed for Clingo.
    Clingo requires lowercase starting atoms or quoted strings.

    Args:
        id_str: The ID string to potentially quote

    Returns:
        The ID, quoted if necessary
    """
    # Always quote if starts with uppercase or contains special chars
    if id_str and (id_str[0].isupper() or any(c in id_str for c in '-_')):
        return f'"{id_str}"'
    return id_str


def parse_atom_args(atom_content: str) -> List[str]:
    """
    Parse arguments from an atom like 'del_att("A","B")' or 'in(x,y)'.
    Handles quoted IDs properly.

    Args:
        atom_content: The content between parentheses, e.g., '"A","B"' or 'x,y'

    Returns:
        List of parsed arguments with quotes removed
    """
    parts = []
    current_part = ""
    in_quotes = False

    for char in atom_content:
        if char == '"':
            in_quotes = not in_quotes
        elif char == ',' and not in_quotes:
            parts.append(current_part.strip('"'))
            current_part = ""
        else:
            current_part += char

    if current_part:
        parts.append(current_part.strip('"'))

    return parts


def parse_binary_atom(atom: str, prefix: str) -> Tuple[str, str]:
    """
    Parse a binary atom like 'del_att("A","B")' into its two arguments.

    Args:
        atom: The full atom string
        prefix: The atom name (e.g., 'del_att', 'add_att')

    Returns:
        Tuple of (first_arg, second_arg)
    """
    if not atom.startswith(f"{prefix}("):
        raise ValueError(f"Atom doesn't start with {prefix}(")

    content = atom[len(prefix)+1:-1]  # Extract content between parens
    parts = parse_atom_args(content)

    if len(parts) != 2:
        raise ValueError(f"Expected 2 arguments in {prefix}, got {len(parts)}")

    return parts[0], parts[1]