#!/usr/bin/env python3
"""
Test quality metrics on saved arguments.
"""

import json
import os
from argir.metrics.quality import compute_quality_metrics, describe_quality


def main():
    results = []

    # Load all saved results
    for filename in sorted(os.listdir('saved-results')):
        if not filename.endswith('.json'):
            continue

        with open(f'saved-results/{filename}', 'r') as f:
            data = json.load(f)

        if not data.get('success'):
            continue

        result = data.get('result', {})
        argir = result.get('argir', {})
        source_text = argir.get('source_text', '')

        # Compute quality metrics
        metrics = compute_quality_metrics(argir)

        # Get FOL result
        fol_summary = result.get('fol_summary', {})
        fol_proved = fol_summary.get('theorem', False) or fol_summary.get('unsat', False)

        results.append({
            'hash': filename.replace('.json', ''),
            'text_preview': source_text[:100] + '...' if len(source_text) > 100 else source_text,
            'metrics': metrics,
            'fol_proved': fol_proved,
        })

    # Sort by overall quality score
    results.sort(key=lambda x: x['metrics']['overall'], reverse=True)

    # Show top 10 highest quality
    print("=" * 80)
    print("TOP 10 HIGHEST QUALITY ARGUMENTS")
    print("=" * 80)
    for i, r in enumerate(results[:10], 1):
        print(f"\n{i}. {r['hash']} (FOL: {'✓' if r['fol_proved'] else '✗'})")
        print(f"   {r['text_preview']}")
        print(f"\n   {describe_quality(r['metrics'])}")

    # Show bottom 10 lowest quality
    print("\n\n" + "=" * 80)
    print("BOTTOM 10 LOWEST QUALITY ARGUMENTS")
    print("=" * 80)
    for i, r in enumerate(results[-10:], 1):
        print(f"\n{i}. {r['hash']} (FOL: {'✓' if r['fol_proved'] else '✗'})")
        print(f"   {r['text_preview']}")
        print(f"\n   {describe_quality(r['metrics'])}")

    # Correlation analysis
    print("\n\n" + "=" * 80)
    print("CORRELATION: Quality Score vs FOL Provability")
    print("=" * 80)

    proved = [r for r in results if r['fol_proved']]
    unproved = [r for r in results if not r['fol_proved']]

    if proved:
        avg_quality_proved = sum(r['metrics']['overall'] for r in proved) / len(proved)
        print(f"Average quality (FOL proved): {avg_quality_proved:.3f}")

    if unproved:
        avg_quality_unproved = sum(r['metrics']['overall'] for r in unproved) / len(unproved)
        print(f"Average quality (FOL unproved): {avg_quality_unproved:.3f}")

    print(f"\nTotal arguments: {len(results)}")
    print(f"FOL proved: {len(proved)} ({len(proved)/len(results)*100:.1f}%)")
    print(f"FOL unproved: {len(unproved)} ({len(unproved)/len(results)*100:.1f}%)")


if __name__ == '__main__':
    main()
