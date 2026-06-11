"""
processor/normalizer.py  (v2)
==============================
Changes:
  - district_zh no longer needs 區 stripped (als_client now delivers it clean)
  - block field added to canonical schema
  - REQUIRED_FIELDS updated to check region_zh OR district_zh (either is enough)
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)


def normalize_record(raw: dict) -> Optional[dict]:
    """
    Canonical schema:
    {
        "region":    {"zh": "九龍",         "en": "Kowloon"},
        "district":  {"zh": "油尖旺",        "en": "Yau Tsim Mong"},
        "street":    {"zh": "彌敦道",        "en": "Nathan Road"},
        "street_no": "100",                  # "100-102" for ranges
        "building":  {"zh": "始創中心",      "en": "Pioneer Centre"},
        "block":     {"zh": "A座",           "en": "Block A"},
        "lat": 22.3098, "lng": 114.1724,
        "_source": "ALS"
    }
    """
    try:
        canonical = {
            "region":    _bi(raw, "region"),
            "district":  _bi(raw, "district"),
            "street":    _bi(raw, "street"),
            "street_no": _street_no(raw.get("street_no_from",""), raw.get("street_no_to","")),
            "building":  _building(raw),
            "block":     {"zh": raw.get("block_zh","").strip(),
                          "en": raw.get("block_en","").strip()},
            "lat":       _float(raw.get("latitude")),
            "lng":       _float(raw.get("longitude")),
            "_source":   "ALS",
        }
    except Exception as e:
        log.debug(f"Normalization error: {e}")
        return None

    # Need at least region OR district in Chinese
    if not canonical["region"]["zh"] and not canonical["district"]["zh"]:
        log.debug(f"Rejected: missing both region_zh and district_zh")
        return None

    return canonical


def _bi(raw, field):
    zh = raw.get(f"{field}_zh", "").strip()
    en = raw.get(f"{field}_en", "").strip()
    # ALS returns ALL-CAPS for English streets/buildings; title-case if fully uppercase
    if en and en == en.upper():
        en = en.title()
    return {"zh": zh, "en": en}


def _street_no(from_: str, to_: str) -> str:
    from_ = str(from_).strip()
    to_   = str(to_).strip()
    if from_ and to_ and from_ != to_:
        return f"{from_}-{to_}"
    return from_


def _building(raw: dict) -> dict:
    """Prefer BuildingName; fall back to EstateName."""
    zh = raw.get("building_zh","").strip() or raw.get("estate_zh","").strip()
    en = raw.get("building_en","").strip() or raw.get("estate_en","").strip()
    if en and en == en.upper():
        en = en.title()
    return {"zh": zh, "en": en}


def _float(val):
    try: return float(val)
    except: return None
