"""
validator/stats.py
===================
Prints a label distribution report for quality checking.
"""

from collections import Counter


def print_distribution_report(all_labels: list):
    total = len(all_labels)
    dist  = Counter(all_labels)

    print("\n" + "="*50)
    print("Label Distribution Report")
    print("="*50)
    print(f"  Total tokens : {total:,}")
    print(f"  Unique labels: {len(dist)}")
    print()
    print(f"  {'Label':<16} {'Count':>7}  {'%':>6}")
    print("  " + "-"*32)

    for label in [
        "O",
        "B-REGION","I-REGION","B-DISTRICT","I-DISTRICT",
        "B-STREET","I-STREET","B-STRNUM","I-STRNUM",
        "B-BUILDING","I-BUILDING","B-FLOOR","I-FLOOR",
        "B-UNIT","I-UNIT",
    ]:
        count = dist.get(label, 0)
        pct   = 100 * count / total if total else 0
        bar   = "█" * int(pct / 2)
        print(f"  {label:<16} {count:>7,}  {pct:>5.1f}%  {bar}")

    o_pct = 100 * dist.get("O", 0) / total if total else 0
    print()
    if o_pct > 35:
        print(f"  ⚠ HIGH O-class ({o_pct:.0f}%). Check parsed fields match address strings.")
    elif o_pct < 5:
        print(f"  ⚠ LOW O-class ({o_pct:.0f}%). Possible over-labeling.")
    else:
        print(f"  ✓ O-class ratio looks healthy ({o_pct:.0f}%).")
    print("="*50 + "\n")
