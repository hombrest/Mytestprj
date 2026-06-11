"""
processor/deduplicator.py
==========================
Removes duplicate canonical records.

Two records are duplicates if they share the same:
    (region_zh, district_zh, street_zh, street_no, building_zh)

Keeps the first occurrence (which has the most complete geo data
since ALS returns best matches first).
"""

import hashlib, json, logging

log = logging.getLogger(__name__)


class Deduplicator:
    def run(self, records: list) -> list:
        seen = set()
        unique = []
        for r in records:
            key = self._key(r)
            if key not in seen:
                seen.add(key)
                unique.append(r)
        log.info(f"Dedup: {len(records)} → {len(unique)} records ({len(records)-len(unique)} removed)")
        return unique

    def _key(self, r: dict) -> str:
        parts = (
            r.get("region",   {}).get("zh",""),
            r.get("district", {}).get("zh",""),
            r.get("street",   {}).get("zh",""),
            r.get("street_no",""),
            r.get("building", {}).get("zh",""),
        )
        return hashlib.md5("|".join(parts).encode()).hexdigest()
