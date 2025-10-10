#!/usr/bin/env python3
"""
Compute statistics on saved ARGIR queries.

This tool analyzes all saved queries in the saved/ directory and computes
statistics about graph structure, detected issues, repairs, and FOL prover results.
"""
from __future__ import annotations

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from server import ArgirRequest, analyze_arguments
from argir.nlp.llm import set_request_api_key


def count_connected_components(graph: Dict[str, Any]) -> int:
    """Count weakly connected components in the argument graph."""
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        return 0

    # Build adjacency list (undirected for weak connectivity)
    adj = defaultdict(set)
    node_ids = {n["id"] for n in nodes}

    for edge in edges:
        src, tgt = edge["source"], edge["target"]
        if src in node_ids and tgt in node_ids:
            adj[src].add(tgt)
            adj[tgt].add(src)

    # DFS to find components
    visited = set()
    components = 0

    def dfs(node_id: str):
        visited.add(node_id)
        for neighbor in adj[node_id]:
            if neighbor not in visited:
                dfs(neighbor)

    for node_id in node_ids:
        if node_id not in visited:
            components += 1
            dfs(node_id)

    return components


def extract_graph_stats(argir: Dict[str, Any]) -> Dict[str, Any]:
    """Extract graph structure statistics."""
    graph = argir.get("graph", {})
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    # Count edge types
    support_edges = sum(1 for e in edges if e.get("kind") == "support")
    attack_edges = sum(1 for e in edges if e.get("kind") == "attack")

    # Graph density (for directed graphs: edges / (nodes * (nodes-1)))
    num_nodes = len(nodes)
    density = 0.0
    if num_nodes > 1:
        max_edges = num_nodes * (num_nodes - 1)
        density = len(edges) / max_edges if max_edges > 0 else 0.0

    return {
        "num_nodes": num_nodes,
        "num_edges": len(edges),
        "support_edges": support_edges,
        "attack_edges": attack_edges,
        "components": count_connected_components(graph),
        "density": density
    }


def extract_diagnosis_stats(issues: List[Dict], repairs: List[Dict]) -> Dict[str, Any]:
    """Extract diagnosis and repair statistics."""
    issue_types = Counter(issue["type"] for issue in issues)

    # Count repair kinds and verification status
    repair_kinds = Counter(repair["kind"] for repair in repairs)
    verified_successful = sum(
        1 for repair in repairs
        if repair.get("verification", {}).get("af_goal_accepted", False)
    )

    return {
        "num_issues": len(issues),
        "issue_types": dict(issue_types),
        "num_repairs": len(repairs),
        "repair_kinds": dict(repair_kinds),
        "verified_successful": verified_successful
    }


def extract_stats_from_result(query_hash: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Extract statistics from a full analysis result (either from cache or fresh analysis)."""
    # Get query parameters (might be in result for old cache format, or need to load separately)
    query_params = result.get("query_params", {})
    if not query_params:
        # Load from saved query file
        file_path = Path("saved") / f"{query_hash}.json"
        if file_path.exists():
            with open(file_path) as f:
                query_params = json.load(f)

    stats = {
        "hash": query_hash,
        "timestamp": query_params.get("timestamp"),
        "settings": {
            "fol_mode": query_params.get("fol_mode"),
            "use_soft": query_params.get("use_soft", False),
            "enable_diagnosis": query_params.get("enable_diagnosis", False),
            "enable_repair": query_params.get("enable_repair", False),
            "k_samples": query_params.get("k_samples", 1)
        },
        "text_length": len(query_params.get("text", "")),
    }

    # Graph statistics
    if result.get("result", {}).get("argir"):
        stats["graph"] = extract_graph_stats(result["result"]["argir"])

    # Diagnosis statistics
    issues = result.get("issues", [])
    repairs = result.get("repairs", [])
    stats["diagnosis"] = extract_diagnosis_stats(issues, repairs)

    # FOL prover status
    fol_summary = result.get("result", {}).get("fol_summary")
    stats["fol_status"] = extract_fol_status(fol_summary)

    # Validation issues
    validation = result.get("validation", {})
    stats["validation"] = {
        "errors": len(validation.get("errors", [])),
        "warnings": len(validation.get("warnings", []))
    }

    return stats


def extract_fol_status(fol_summary: Optional[Dict[str, Any]]) -> str:
    """Extract FOL prover status from summary.

    Returns one of: 'theorem', 'unsat', 'sat', 'timeout', 'unknown', 'none'
    Following the same logic as argir/report/render.py
    """
    if not fol_summary:
        return "none"

    # Check in the same order as the report renderer
    if fol_summary.get("theorem"):
        return "theorem"  # Conjecture proved (best case)
    elif fol_summary.get("unsat"):
        return "unsat"  # Unsatisfiable (axioms contradict negated goal, i.e., goal proven)
    elif fol_summary.get("sat"):
        return "sat"  # Satisfiable (goal not proven, countermodel exists)
    elif fol_summary.get("note"):
        note = fol_summary["note"]
        if "timeout" in note.lower():
            return "timeout"
        return "unknown"

    # Check raw output for timeout
    raw = fol_summary.get("raw", "")
    if "Timeout" in raw or "timeout" in raw.lower():
        return "timeout"

    # If neither sat nor unsat, it's unknown
    return "unknown"


def analyze_saved_query(query_hash: str, api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Analyze a saved query and return statistics.

    First checks for cached results in saved-results/, otherwise re-runs analysis.
    """
    file_path = Path("saved") / f"{query_hash}.json"
    if not file_path.exists():
        print(f"Warning: {query_hash}.json not found", file=sys.stderr)
        return None

    # Check for cached results first
    results_path = Path("saved-results") / f"{query_hash}.json"
    if results_path.exists():
        try:
            with open(results_path) as f:
                result = json.load(f)
            # Extract statistics from cached result
            return extract_stats_from_result(query_hash, result)
        except Exception as e:
            print(f"Warning: Failed to load cached results for {query_hash}, re-running: {e}", file=sys.stderr)

    # No cache found, run analysis
    try:
        # Load query parameters
        with open(file_path) as f:
            query_params = json.load(f)

        # Set API key if provided
        if api_key:
            set_request_api_key(api_key)

        # Create request and run analysis
        req = ArgirRequest(
            text=query_params.get("text", ""),
            fol_mode=query_params.get("fol_mode", "classical"),
            goal_id=query_params.get("goal_id"),
            goal_hint=query_params.get("goal_hint"),
            use_soft=query_params.get("use_soft", False),
            k_samples=query_params.get("k_samples", 1),
            enable_diagnosis=query_params.get("enable_diagnosis", False),
            enable_repair=query_params.get("enable_repair", False),
            semantics=query_params.get("semantics", "grounded"),
            max_af_edits=query_params.get("max_af_edits", 2),
            max_abduce=query_params.get("max_abduce", 2)
        )

        result = analyze_arguments(req)

        # Extract statistics using the helper function
        return extract_stats_from_result(query_hash, result)

    except Exception as e:
        print(f"Error analyzing {query_hash}: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def aggregate_stats(all_stats: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute aggregate statistics from all queries."""
    if not all_stats:
        return {}

    # Helper functions for safe aggregation
    def safe_avg(values):
        return sum(values) / len(values) if values else 0

    def safe_min(values):
        return min(values) if values else 0

    def safe_max(values):
        return max(values) if values else 0

    # Settings distribution
    fol_modes = Counter(s["settings"]["fol_mode"] for s in all_stats)
    use_soft = Counter(s["settings"]["use_soft"] for s in all_stats)
    enable_diagnosis = Counter(s["settings"]["enable_diagnosis"] for s in all_stats)

    # Graph statistics
    graph_stats = [s["graph"] for s in all_stats if "graph" in s]
    nodes = [g["num_nodes"] for g in graph_stats]
    edges = [g["num_edges"] for g in graph_stats]
    components = [g["components"] for g in graph_stats]
    densities = [g["density"] for g in graph_stats]
    support_edges = [g["support_edges"] for g in graph_stats]
    attack_edges = [g["attack_edges"] for g in graph_stats]
    total_support = sum(support_edges)
    total_attack = sum(attack_edges)

    # Issue types (aggregate across all queries)
    all_issue_types = Counter()
    for s in all_stats:
        if "diagnosis" in s:
            for issue_type, count in s["diagnosis"].get("issue_types", {}).items():
                all_issue_types[issue_type] += count

    # Repair statistics
    issues_per_query = [s["diagnosis"]["num_issues"] for s in all_stats if "diagnosis" in s]
    repairs_per_query = [s["diagnosis"]["num_repairs"] for s in all_stats if "diagnosis" in s]
    verified_per_query = [s["diagnosis"]["verified_successful"] for s in all_stats if "diagnosis" in s]

    total_issues = sum(issues_per_query)
    total_repairs = sum(repairs_per_query)
    total_verified = sum(verified_per_query)

    # Count queries with no issues
    queries_with_no_issues = sum(1 for count in issues_per_query if count == 0)

    # Aggregate repair kinds
    all_repair_kinds = Counter()
    for s in all_stats:
        if "diagnosis" in s:
            for kind, count in s["diagnosis"].get("repair_kinds", {}).items():
                all_repair_kinds[kind] += count

    # FOL status distribution
    fol_statuses = Counter(s["fol_status"] for s in all_stats)

    # Text length statistics
    text_lengths = [s["text_length"] for s in all_stats]

    # Correlations
    # Prepare data for correlation analysis
    queries_with_all_data = []
    for s in all_stats:
        if "graph" in s and "diagnosis" in s:
            queries_with_all_data.append({
                "nodes": s["graph"]["num_nodes"],
                "edges": s["graph"]["num_edges"],
                "components": s["graph"]["components"],
                "issues": s["diagnosis"]["num_issues"],
                "text_length": s["text_length"],
                "fol_proved": 1 if s["fol_status"] == "theorem" else 0
            })

    # Compute simple correlations (queries with issues vs without)
    if queries_with_all_data:
        queries_with_issues = [q for q in queries_with_all_data if q["issues"] > 0]
        queries_without_issues = [q for q in queries_with_all_data if q["issues"] == 0]

        avg_nodes_with_issues = safe_avg([q["nodes"] for q in queries_with_issues]) if queries_with_issues else 0
        avg_nodes_without_issues = safe_avg([q["nodes"] for q in queries_without_issues]) if queries_without_issues else 0

        avg_edges_with_issues = safe_avg([q["edges"] for q in queries_with_issues]) if queries_with_issues else 0
        avg_edges_without_issues = safe_avg([q["edges"] for q in queries_without_issues]) if queries_without_issues else 0

        avg_components_with_issues = safe_avg([q["components"] for q in queries_with_issues]) if queries_with_issues else 0
        avg_components_without_issues = safe_avg([q["components"] for q in queries_without_issues]) if queries_without_issues else 0

        # FOL provability by connectedness
        proved_queries = [q for q in queries_with_all_data if q["fol_proved"] == 1]
        unproved_queries = [q for q in queries_with_all_data if q["fol_proved"] == 0]

        avg_components_proved = safe_avg([q["components"] for q in proved_queries]) if proved_queries else 0
        avg_components_unproved = safe_avg([q["components"] for q in unproved_queries]) if unproved_queries else 0
    else:
        avg_nodes_with_issues = avg_nodes_without_issues = 0
        avg_edges_with_issues = avg_edges_without_issues = 0
        avg_components_with_issues = avg_components_without_issues = 0
        avg_components_proved = avg_components_unproved = 0

    # Timestamps
    timestamps = [s["timestamp"] for s in all_stats if s.get("timestamp")]
    timestamps.sort()

    def safe_avg(values):
        return sum(values) / len(values) if values else 0

    def safe_min(values):
        return min(values) if values else 0

    def safe_max(values):
        return max(values) if values else 0

    return {
        "total_queries": len(all_stats),
        "date_range": {
            "earliest": timestamps[0] if timestamps else None,
            "latest": timestamps[-1] if timestamps else None
        },
        "settings": {
            "fol_mode": dict(fol_modes),
            "use_soft": dict(use_soft),
            "enable_diagnosis": dict(enable_diagnosis)
        },
        "graph": {
            "nodes": {
                "avg": safe_avg(nodes),
                "min": safe_min(nodes),
                "max": safe_max(nodes)
            },
            "edges": {
                "avg": safe_avg(edges),
                "min": safe_min(edges),
                "max": safe_max(edges)
            },
            "edge_types": {
                "support": total_support,
                "attack": total_attack,
                "support_pct": total_support / (total_support + total_attack) * 100 if (total_support + total_attack) > 0 else 0
            },
            "components": {
                "avg": safe_avg(components)
            },
            "density": {
                "avg": safe_avg(densities)
            }
        },
        "diagnosis": {
            "total_issues": total_issues,
            "issue_types": dict(all_issue_types),
            "issues_per_query": {
                "avg": safe_avg(issues_per_query),
                "min": safe_min(issues_per_query),
                "max": safe_max(issues_per_query)
            },
            "total_repairs": total_repairs,
            "repairs_per_query": {
                "avg": safe_avg(repairs_per_query),
                "min": safe_min(repairs_per_query),
                "max": safe_max(repairs_per_query)
            },
            "verified_successful": total_verified,
            "verified_per_query": {
                "avg": safe_avg(verified_per_query),
                "min": safe_min(verified_per_query),
                "max": safe_max(verified_per_query)
            },
            "success_rate": total_verified / total_repairs if total_repairs > 0 else 0,
            "queries_with_no_issues": queries_with_no_issues,
            "repair_kinds": dict(all_repair_kinds)
        },
        "correlations": {
            "complexity_vs_issues": {
                "with_issues": {
                    "avg_nodes": avg_nodes_with_issues,
                    "avg_edges": avg_edges_with_issues,
                    "avg_components": avg_components_with_issues
                },
                "without_issues": {
                    "avg_nodes": avg_nodes_without_issues,
                    "avg_edges": avg_edges_without_issues,
                    "avg_components": avg_components_without_issues
                }
            },
            "connectedness_vs_provability": {
                "proved_avg_components": avg_components_proved,
                "unproved_avg_components": avg_components_unproved
            }
        },
        "fol_status": dict(fol_statuses),
        "text_length": {
            "avg": safe_avg(text_lengths),
            "min": safe_min(text_lengths),
            "max": safe_max(text_lengths)
        }
    }


def format_summary_text(agg: Dict[str, Any]) -> str:
    """Format aggregate statistics as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("ARGIR Saved Queries Statistics")
    lines.append("=" * 60)
    lines.append(f"Total queries: {agg['total_queries']}")

    if agg['date_range']['earliest']:
        lines.append(f"Date range: {agg['date_range']['earliest'][:10]} to {agg['date_range']['latest'][:10]}")

    lines.append("")
    lines.append("Query Settings:")
    lines.append(f"  FOL mode: {', '.join(f'{k} ({v})' for k, v in agg['settings']['fol_mode'].items())}")
    lines.append(f"  Soft pipeline: {', '.join(f'{k} ({v})' for k, v in agg['settings']['use_soft'].items())}")
    lines.append(f"  Diagnosis: {', '.join(f'{k} ({v})' for k, v in agg['settings']['enable_diagnosis'].items())}")

    lines.append("")
    lines.append("Graph Statistics:")
    g = agg['graph']
    lines.append(f"  Nodes: avg={g['nodes']['avg']:.1f}, min={g['nodes']['min']}, max={g['nodes']['max']}")
    lines.append(f"  Edges: avg={g['edges']['avg']:.1f}, min={g['edges']['min']}, max={g['edges']['max']}")
    et = g['edge_types']
    lines.append(f"  Edge types: {et['support']} support ({et['support_pct']:.1f}%), {et['attack']} attack")
    lines.append(f"  Components: avg={g['components']['avg']:.2f}")
    lines.append(f"  Density: avg={g['density']['avg']:.3f}")

    lines.append("")
    lines.append("Issues Found:")
    d = agg['diagnosis']
    lines.append(f"  Total issues: {d['total_issues']}")
    lines.append(f"  Queries with no issues: {d['queries_with_no_issues']} ({d['queries_with_no_issues']/agg['total_queries']*100:.1f}%)")
    ip = d['issues_per_query']
    lines.append(f"  Per query: avg={ip['avg']:.1f}, min={ip['min']}, max={ip['max']}")
    if d['issue_types']:
        lines.append("  By type:")
        for issue_type, count in sorted(d['issue_types'].items(), key=lambda x: -x[1]):
            lines.append(f"    - {issue_type}: {count}")

    lines.append("")
    lines.append("Repairs Generated:")
    lines.append(f"  Total repairs: {d['total_repairs']}")
    rp = d['repairs_per_query']
    lines.append(f"  Per query: avg={rp['avg']:.1f}, min={rp['min']}, max={rp['max']}")
    if d.get('repair_kinds'):
        lines.append(f"  By kind: {', '.join(f'{k} ({v})' for k, v in d['repair_kinds'].items())}")
    lines.append(f"  Verified successful: {d['verified_successful']} ({d['success_rate']*100:.1f}%)")
    vp = d['verified_per_query']
    lines.append(f"  Verified per query: avg={vp['avg']:.1f}, min={vp['min']}, max={vp['max']}")

    lines.append("")
    lines.append("FOL Prover Results:")
    for status, count in sorted(agg['fol_status'].items(), key=lambda x: -x[1]):
        pct = count / agg['total_queries'] * 100
        status_label = {
            'theorem': 'Theorem (proved)',
            'unsat': 'Unsat (proved)',
            'sat': 'Sat (countermodel)',
            'unknown': 'Unknown',
            'timeout': 'Timeout',
            'none': 'None'
        }.get(status, status.capitalize())
        lines.append(f"  {status_label}: {count} ({pct:.1f}%)")

    lines.append("")
    lines.append("Text Statistics:")
    t = agg['text_length']
    lines.append(f"  Length: avg={t['avg']:.0f} chars, min={t['min']}, max={t['max']}")

    lines.append("")
    lines.append("Correlations & Insights:")
    corr = agg['correlations']
    cvi = corr['complexity_vs_issues']
    lines.append(f"  Graph complexity vs issues:")
    lines.append(f"    Queries WITH issues: avg {cvi['with_issues']['avg_nodes']:.1f} nodes, {cvi['with_issues']['avg_edges']:.1f} edges")
    lines.append(f"    Queries WITHOUT issues: avg {cvi['without_issues']['avg_nodes']:.1f} nodes, {cvi['without_issues']['avg_edges']:.1f} edges")

    cvp = corr['connectedness_vs_provability']
    lines.append(f"  Graph connectedness vs FOL provability:")
    lines.append(f"    Proved queries: avg {cvp['proved_avg_components']:.2f} components")
    lines.append(f"    Unproved queries: avg {cvp['unproved_avg_components']:.2f} components")

    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Compute statistics on saved ARGIR queries"
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        default=True,
        help="Show aggregate statistics (default)"
    )
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Show per-query statistics"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "csv"],
        default="text",
        help="Output format"
    )
    parser.add_argument(
        "--filter",
        type=str,
        help="Only analyze specific query hash(es), comma-separated"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Write to file instead of stdout"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="Gemini API key (optional, for queries requiring LLM calls)"
    )

    args = parser.parse_args()

    # Find all saved queries
    saved_dir = Path("saved")
    if not saved_dir.exists():
        print("Error: saved/ directory not found", file=sys.stderr)
        return 1

    # Get list of queries to analyze
    if args.filter:
        query_hashes = [h.strip() for h in args.filter.split(",")]
    else:
        query_hashes = [f.stem for f in saved_dir.glob("*.json")]

    print(f"Analyzing {len(query_hashes)} queries...", file=sys.stderr)

    # Analyze each query
    all_stats = []
    for i, query_hash in enumerate(query_hashes, 1):
        print(f"  [{i}/{len(query_hashes)}] {query_hash}...", file=sys.stderr)
        stats = analyze_saved_query(query_hash, args.api_key)
        if stats:
            all_stats.append(stats)

    print(f"Successfully analyzed {len(all_stats)} queries", file=sys.stderr)

    # Generate output
    output_text = ""

    if args.detailed and args.format == "json":
        output_text = json.dumps(all_stats, indent=2)
    elif args.detailed and args.format == "csv":
        # CSV output for detailed stats
        import csv
        import io

        output = io.StringIO()
        if all_stats:
            # Flatten stats for CSV
            fieldnames = ["hash", "timestamp", "fol_mode", "use_soft", "num_nodes",
                         "num_edges", "components", "num_issues", "num_repairs", "fol_status"]
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for s in all_stats:
                row = {
                    "hash": s["hash"],
                    "timestamp": s.get("timestamp", ""),
                    "fol_mode": s["settings"]["fol_mode"],
                    "use_soft": s["settings"]["use_soft"],
                    "num_nodes": s.get("graph", {}).get("num_nodes", 0),
                    "num_edges": s.get("graph", {}).get("num_edges", 0),
                    "components": s.get("graph", {}).get("components", 0),
                    "num_issues": s.get("diagnosis", {}).get("num_issues", 0),
                    "num_repairs": s.get("diagnosis", {}).get("num_repairs", 0),
                    "fol_status": s.get("fol_status", "unknown")
                }
                writer.writerow(row)

        output_text = output.getvalue()
    else:
        # Summary statistics
        agg = aggregate_stats(all_stats)

        if args.format == "json":
            output_text = json.dumps(agg, indent=2)
        else:  # text format
            output_text = format_summary_text(agg)

    # Write output
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output_text)
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
