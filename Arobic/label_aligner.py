"""
validator/label_aligner.py
===========================
Produces character-level BIO labels and validates alignment.

Labels:
    O            Outside any field
    B-REGION     Beginning of region (香港/Kowloon/NT)
    I-REGION
    B-DISTRICT   Beginning of district
    I-DISTRICT
    B-STREET
    I-STREET
    B-STRNUM     Street number (including ranges like 12-16)
    I-STRNUM
    B-BUILDING
    I-BUILDING
    B-FLOOR
    I-FLOOR
    B-UNIT
    I-UNIT

Key design choices:
  - Spaces INSIDE multi-word English fields are labeled I-<FIELD>
  - Suffix chars (號, /F, 室, Rm) are labeled O — they are not the value
  - Processing order: longest/most-specific fields first to avoid overlap
  - Both zh and en values for each field are searched; whichever appears
    in the address string gets tagged (handles mixed-script variants)
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

LABELS = [
    "O",
    "B-REGION",   "I-REGION",
    "B-DISTRICT", "I-DISTRICT",
    "B-STREET",   "I-STREET",
    "B-STRNUM",   "I-STRNUM",
    "B-BUILDING", "I-BUILDING",
    "B-FLOOR",    "I-FLOOR",
    "B-UNIT",     "I-UNIT",
]
LABEL2ID = {l: i for i, l in enumerate(LABELS)}
ID2LABEL = {i: l for l, i in LABEL2ID.items()}

# Field name → (parsed key zh, parsed key en, B-tag, I-tag)
# Processed in this order — longer fields first to avoid shorter ones
# claiming characters that belong to a longer span.
FIELD_SPEC = [
    ("building_zh", "building_en", "B-BUILDING", "I-BUILDING"),
    ("street_zh",   "street_en",   "B-STREET",   "I-STREET"),
    ("district_zh", "district_en", "B-DISTRICT", "I-DISTRICT"),
    ("region_zh",   "region_en",   "B-REGION",   "I-REGION"),
    ("street_no",   None,          "B-STRNUM",   "I-STRNUM"),
    ("floor",       None,          "B-FLOOR",    "I-FLOOR"),
    ("unit",        None,          "B-UNIT",     "I-UNIT"),
]


def align_labels(address: str, parsed: dict) -> list:
    """
    Returns a list of label strings, one per character, same length as address.

    Example
    -------
    address = "九龍旺角彌敦道100號始創中心23/F2301室"
    parsed  = {"region_zh": "九龍", "district_zh": "旺角",
               "street_zh": "彌敦道", "street_no": "100",
               "building_zh": "始創中心", "floor": "23", "unit": "2301"}
    → ["B-REGION","I-REGION","B-DISTRICT","I-DISTRICT",
       "B-STREET","I-STREET","I-STREET",
       "B-STRNUM","I-STRNUM","I-STRNUM","O",
       "B-BUILDING","I-BUILDING","I-BUILDING","I-BUILDING",
       "B-FLOOR","I-FLOOR","O",
       "B-UNIT","I-UNIT","I-UNIT","I-UNIT","O"]
    """
    labels = ["O"] * len(address)

    for zh_key, en_key, b_tag, i_tag in FIELD_SPEC:
        # Try both scripts; tag whichever appears first in the address
        candidates = []
        v_zh = parsed.get(zh_key, "").strip() if zh_key else ""
        v_en = parsed.get(en_key, "").strip() if en_key else ""

        for value in [v_zh, v_en]:
            if not value:
                continue
            # Find ALL occurrences
            start = 0
            while True:
                idx = address.find(value, start)
                if idx == -1:
                    break
                candidates.append((idx, value))
                start = idx + 1

        if not candidates:
            continue

        # Pick the leftmost occurrence that is still untagged
        candidates.sort(key=lambda x: x[0])
        for idx, value in candidates:
            span = range(idx, idx + len(value))
            if all(labels[i] == "O" for i in span):
                labels[idx] = b_tag
                for i in range(idx + 1, idx + len(value)):
                    labels[i] = i_tag
                break  # Tag only one occurrence per field

    return labels


def validate_alignment(address: str, labels: list, parsed: dict) -> list:
    """
    Returns a list of error strings (empty = all good).
    Checks that every non-empty parsed field value is tagged correctly.
    """
    errors = []

    FIELD_CHECK = [
        ("region_zh",   "REGION"),
        ("district_zh", "DISTRICT"),
        ("street_zh",   "STREET"),
        ("street_no",   "STRNUM"),
        ("building_zh", "BUILDING"),
        ("floor",       "FLOOR"),
        ("unit",        "UNIT"),
    ]

    for key, tag in FIELD_CHECK:
        value = parsed.get(key, "").strip()
        if not value:
            continue

        idx = address.find(value)
        if idx == -1:
            # Not found — could be English variant was used; not an error
            continue

        expected_b = f"B-{tag}"
        expected_i = f"I-{tag}"

        if labels[idx] != expected_b:
            errors.append(
                f"Field {key!r}: char {idx} ({address[idx]!r}) "
                f"expected {expected_b}, got {labels[idx]!r}"
            )
            continue

        for j in range(idx + 1, idx + len(value)):
            if labels[j] != expected_i:
                errors.append(
                    f"Field {key!r}: char {j} ({address[j]!r}) "
                    f"expected {expected_i}, got {labels[j]!r}"
                )
                break

    return errors


def visualize(address: str, labels: list):
    """Debug helper — pretty-prints char/label table."""
    print(f"\nAddress ({len(address)} chars): {address}")
    print(f"{'#':>3}  {'Char':^5}  Label")
    print("─" * 30)
    for i, (ch, lb) in enumerate(zip(address, labels)):
        marker = "" if lb == "O" else f"  ← {lb}"
        print(f"{i:>3}  {ch:^5}  {lb:<12}{marker}")
