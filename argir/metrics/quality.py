"""
Graph quality metrics for arguments.

Measures structural properties that indicate "good" argumentation,
independent of logical validity.
"""

from typing import Dict, List, Tuple
import networkx as nx


def compute_quality_metrics(argir: dict) -> Dict[str, float]:
    """
    Compute structural quality metrics for an argument graph.

    Returns dict with:
    - tree_score: How tree-like (many premises → few conclusions)
    - density_score: How densely connected
    - redundancy_score: Multiple paths to conclusion
    - balance_score: Not just linear chain
    - overall_score: Combined metric
    """
    graph = argir['graph']
    nodes = graph['nodes']
    edges = graph['edges']
    goal_id = argir.get('metadata', {}).get('goal_id')

    if not nodes:
        return {k: 0.0 for k in ['tree', 'density', 'redundancy', 'balance', 'overall']}

    # Build directed graph (support edges only)
    G = nx.DiGraph()
    for node in nodes:
        G.add_node(node['id'])

    for edge in edges:
        if edge['kind'] == 'support':
            G.add_edge(edge['source'], edge['target'])

    # Metrics
    tree = compute_tree_score(G, goal_id)
    density = compute_density_score(G)
    redundancy = compute_redundancy_score(G, goal_id)
    balance = compute_balance_score(G)

    overall = (tree + density + redundancy + balance) / 4.0

    return {
        'tree': tree,
        'density': density,
        'redundancy': redundancy,
        'balance': balance,
        'overall': overall
    }


def compute_tree_score(G: nx.DiGraph, goal_id: str = None) -> float:
    """
    Tree-likeness: Many premises (sources) converging to few conclusions (sinks).

    Good: 5 premises → 2 intermediate → 1 conclusion (inverted tree)
    Bad: 1 premise → 1 → 1 → 1 → 1 conclusion (linear)

    Returns 0.0-1.0, higher is more tree-like.
    """
    if len(G.nodes()) == 0:
        return 0.0

    sources = [n for n in G.nodes() if G.in_degree(n) == 0]  # Premises
    sinks = [n for n in G.nodes() if G.out_degree(n) == 0]   # Conclusions

    if not sinks:
        return 0.0

    # Ratio of sources to sinks (higher = more tree-like)
    ratio = len(sources) / len(sinks)

    # Normalize: 3+ sources per sink = perfect score
    score = min(ratio / 3.0, 1.0)

    return score


def compute_density_score(G: nx.DiGraph) -> float:
    """
    Connection density: How connected is the graph?

    Good: Many edges connecting nodes (dense argumentation)
    Bad: Sparse, disconnected fragments

    Returns 0.0-1.0, higher is denser.
    """
    n = len(G.nodes())
    if n <= 1:
        return 0.0

    actual_edges = len(G.edges())
    max_possible = n * (n - 1)  # Directed graph, no self-loops

    if max_possible == 0:
        return 0.0

    density = actual_edges / max_possible

    # Normalize: 20% density is very good for argument graphs
    score = min(density / 0.2, 1.0)

    return score


def compute_redundancy_score(G: nx.DiGraph, goal_id: str = None) -> float:
    """
    Redundant support: Multiple independent paths to conclusion.

    Good: Conclusion has 3 different supporting chains
    Bad: Conclusion depends on single chain (brittle)

    Returns 0.0-1.0, higher is more redundant.
    """
    if goal_id is None or goal_id not in G.nodes():
        # Use any sink node
        sinks = [n for n in G.nodes() if G.out_degree(n) == 0]
        if not sinks:
            return 0.0
        goal_id = sinks[0]

    # Count independent paths from sources to goal
    sources = [n for n in G.nodes() if G.in_degree(n) == 0]

    if not sources:
        return 0.0

    # Count paths
    path_count = 0
    for source in sources:
        try:
            if nx.has_path(G, source, goal_id):
                # Count all simple paths
                paths = list(nx.all_simple_paths(G, source, goal_id))
                path_count += len(paths)
        except:
            pass

    # Normalize: 3+ paths = perfect score
    score = min(path_count / 3.0, 1.0)

    return score


def compute_balance_score(G: nx.DiGraph) -> float:
    """
    Balance: Not overly linear, has branching and convergence.

    Good: Mix of branching (1→many) and convergence (many→1)
    Bad: Pure linear chain (1→1→1→1)

    Returns 0.0-1.0, higher is more balanced.
    """
    if len(G.nodes()) <= 2:
        return 1.0  # Too small to judge

    # Count node types
    linear_nodes = 0  # in_degree=1, out_degree=1
    branch_nodes = 0  # out_degree > 1
    converge_nodes = 0  # in_degree > 1

    for node in G.nodes():
        in_deg = G.in_degree(node)
        out_deg = G.out_degree(node)

        if in_deg == 1 and out_deg == 1:
            linear_nodes += 1
        if out_deg > 1:
            branch_nodes += 1
        if in_deg > 1:
            converge_nodes += 1

    total = len(G.nodes())
    linear_ratio = linear_nodes / total

    # Balanced = some branching, some convergence, not all linear
    has_structure = (branch_nodes + converge_nodes) / total

    # Score: low linear ratio, high structure ratio
    score = (1.0 - linear_ratio) * has_structure

    return score


def describe_quality(metrics: Dict[str, float]) -> str:
    """
    Generate human-readable description of quality metrics.
    """
    lines = []

    if metrics['tree'] > 0.7:
        lines.append("✓ Well-structured inverted tree (many premises → conclusion)")
    elif metrics['tree'] < 0.3:
        lines.append("✗ Linear structure (few premises)")

    if metrics['density'] > 0.7:
        lines.append("✓ Densely connected (rich argumentation)")
    elif metrics['density'] < 0.3:
        lines.append("✗ Sparse connections (disconnected claims)")

    if metrics['redundancy'] > 0.7:
        lines.append("✓ Multiple independent paths to conclusion (robust)")
    elif metrics['redundancy'] < 0.3:
        lines.append("✗ Single-path dependency (brittle)")

    if metrics['balance'] > 0.7:
        lines.append("✓ Balanced structure (branching and convergence)")
    elif metrics['balance'] < 0.3:
        lines.append("✗ Linear chain (no branching)")

    overall = metrics['overall']
    if overall > 0.7:
        summary = "Overall: Strong argumentative structure"
    elif overall > 0.4:
        summary = "Overall: Moderate argumentative structure"
    else:
        summary = "Overall: Weak argumentative structure"

    lines.append(f"\n{summary} (score: {overall:.2f})")

    return "\n".join(lines)
