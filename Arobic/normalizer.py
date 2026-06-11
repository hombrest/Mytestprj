"""
processor/normalizer.py
========================
Cleans raw ALS records into canonical form.

Canonical schema:
{
    "region":    {"zh": "九龍",       "en": "Kowloon"},
    "district":  {"zh": "油尖旺",     "en": "Yau Tsim Mong"},
    "street":    {"zh": "彌敦道",     "en": "Nathan Road"},
    "street_no": "100",               # "100-102" for ranges
    "building":  {"zh": "始創中心",   "en": "Pioneer Centre"},
    "lat": 22.3098, "lng": 114.1724,
    "_source": "ALS"
}
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)


def normalize_record(raw: dict) -> Optional[dict]:
    try:
        canonical = {
            "region":    _bi(raw, "region"),
            "district":  _bi(raw, "district"),
            "street":    _bi(raw, "street"),
            "street_no": _street_no(raw.get("street_no_from",""), raw.get("street_no_to","")),
            "building":  _building(raw),
            "lat":       _float(raw.get("latitude")),
            "lng":       _float(raw.get("longitude")),
            "_source":   "ALS",
        }
    except Exception as e:
        log.debug(f"Normalization error: {e}")
        return None

    # Require at least region+district in Chinese
    if not canonical["region"]["zh"] or not canonical["district"]["zh"]:
        return None
    return canonical


def _bi(raw, field):
    zh = raw.get(f"{field}_zh", "").strip()
    en = raw.get(f"{field}_en", "").strip()
    # ALS returns ALL-CAPS for English; only title-case if fully uppercase
    if en == en.upper():
        en = en.title()
    return {"zh": zh, "en": en}


def _street_no(from_: str, to_: str) -> str:
    from_ = from_.strip(); to_ = to_.strip()
    if from_ and to_ and from_ != to_:
        return f"{from_}-{to_}"
    return from_


def _building(raw: dict) -> dict:
    # Prefer BuildingName; fall back to EstateName
    zh = raw.get("building_zh","").strip() or raw.get("estate_zh","").strip()
    en = raw.get("building_en","").strip() or raw.get("estate_en","").strip()
    if en == en.upper(): en = en.title()
    return {"zh": zh, "en": en}


def _float(val):
    try: return float(val)
    except: return None
