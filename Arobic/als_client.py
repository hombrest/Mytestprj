"""
extractor/als_client.py  (v2 — fixed against ALS Data Dictionary v3.2)
========================================================================
Changes from v1:
  FIX 1+4: DcDistrict is a FULL NAME ("Yau Tsim Mong District"), not a code.
           Replaced fake DISTRICT_CODE_MAP with DISTRICT_EN_TO_ZH keyed on
           the real values the API returns.
  FIX 2:   ChiDistrict.DcDistrict returns e.g. "油尖旺區" (with 區 suffix).
           Strip the trailing 區 so it matches address substrings like "油尖旺".
  FIX 3:   region_zh now reads chi["Region"] directly (already inside
           ChiPremisesAddress) rather than relying on a fallback chain.
  FIX 5:   Village addresses: fall back to EngVillage/ChiVillage when
           EngStreet/ChiStreet are absent.
  FIX 6:   Block info extracted (BlockDescriptor + BlockNo → e.g. "Block A").
  FIX 7:   LocationName inside EngStreet/ChiStreet is now read.

Real ALS JSON structure (verified against v3.2 spec):
{
  "SuggestedAddress": [{
    "Address": {
      "PremisesAddress": {
        "EngPremisesAddress": {
          "Region": "KLN",                          ← "HK" | "KLN" | "NT"
          "EngDistrict": {
            "DcDistrict": "Yau Tsim Mong District"  ← FULL NAME, not a code
          },
          "EngStreet": {
            "LocationName": "...",                  ← place name (optional)
            "StreetName": "NATHAN ROAD",
            "BuildingNoFrom": "100",
            "BuildingNoTo": ""
          },
          "EngVillage": {                           ← present for NT village addrs
            "LocationName": "...",
            "VillageName": "TAI PO TUI",
            "BuildingNoFrom": "3",
            "BuildingNoTo": ""
          },
          "EngBlock": {                             ← present for estates
            "BlockDescriptor": "Block",
            "BlockNo": "A"
          },
          "BuildingName": "PIONEER CENTRE",
          "EngEstate": {"EstateName": "..."}
        },
        "ChiPremisesAddress": {
          "Region": "九龍",                          ← Chinese region text directly
          "ChiDistrict": {
            "DcDistrict": "油尖旺區"                 ← includes 區 suffix
          },
          "ChiStreet": {
            "LocationName": "...",
            "StreetName": "彌敦道",
            "BuildingNoFrom": "100",
            "BuildingNoTo": ""
          },
          "ChiVillage": {
            "VillageName": "大埔滘",
            "BuildingNoFrom": "3"
          },
          "ChiBlock": {
            "BlockDescriptor": "座",
            "BlockNo": "A"
          },
          "BuildingName": "始創中心",
          "ChiEstate": {"EstateName": "..."}
        },
        "GeospatialInformation": [{"Latitude": 22.3, "Longitude": 114.17}]
      }
    }
  }]
}
"""

import json, logging, time, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from typing import Optional

log = logging.getLogger(__name__)
ALS_BASE = "https://www.als.gov.hk/lookup"

# Keys are the EXACT DcDistrict strings ALS returns for EngPremisesAddress.
# Values are the Chinese district name WITHOUT the trailing 區.
DISTRICT_EN_TO_ZH = {
    "Central & Western District": "中西區",
    "Eastern District":           "東區",
    "Islands District":           "離島區",
    "Kowloon City District":      "九龍城區",
    "Kwai Tsing District":        "葵青區",
    "Kwun Tong District":         "觀塘區",
    "North District":             "北區",
    "Sai Kung District":          "西貢區",
    "Sha Tin District":           "沙田區",
    "Sham Shui Po District":      "深水埗區",
    "Southern District":          "南區",
    "Tai Po District":            "大埔區",
    "Tsuen Wan District":         "荃灣區",
    "Tuen Mun District":          "屯門區",
    "Wan Chai District":          "灣仔區",
    "Wong Tai Sin District":      "黃大仙區",
    "Yau Tsim Mong District":     "油尖旺區",
    "Yuen Long District":         "元朗區",
}

REGION_CODE_TO_ZH = {
    "HK":  "香港",
    "KLN": "九龍",
    "NT":  "新界",
}
REGION_CODE_TO_EN = {
    "HK":  "Hong Kong",
    "KLN": "Kowloon",
    "NT":  "New Territories",
}


class ALSClient:
    def __init__(self, n_results=20, delay=0.5, use_json=True):
        self.n_results = n_results
        self.delay     = delay
        self.use_json  = use_json

    def query(self, term: str) -> list:
        params = urllib.parse.urlencode({"q": term, "n": self.n_results})
        url    = f"{ALS_BASE}?{params}"
        req    = urllib.request.Request(url, headers={
            "Accept":          "application/json",
            "Accept-Language": "zh-Hant,en",
            "User-Agent":      "HKAddressPipeline/2.0 (research)",
        })
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read()
        except Exception as e:
            log.error(f"HTTP error for '{term}': {e}")
            return []
        time.sleep(self.delay)
        try:
            return self._parse_json(raw) if self.use_json else self._parse_xml(raw)
        except Exception as e:
            log.warning(f"Parse error for '{term}': {e}")
            return []

    # ── JSON parsing ───────────────────────────────────────────────────────

    def _parse_json(self, raw: bytes) -> list:
        data    = json.loads(raw.decode("utf-8"))
        records = []
        for item in data.get("SuggestedAddress", []):
            try:
                paddr = item["Address"]["PremisesAddress"]
                r = self._extract_json(paddr)
                if r:
                    records.append(r)
            except (KeyError, TypeError):
                continue
        return records

    def _extract_json(self, paddr: dict) -> Optional[dict]:
        eng = paddr.get("EngPremisesAddress") or {}
        chi = paddr.get("ChiPremisesAddress") or {}
        geo = paddr.get("GeospatialInformation") or [{}]
        if isinstance(geo, dict):
            geo = [geo]

        # ── Region ────────────────────────────────────────────────────────
        region_code = eng.get("Region", "")          # "HK" | "KLN" | "NT"
        region_en   = REGION_CODE_TO_EN.get(region_code, region_code)
        region_zh   = chi.get("Region", "")          # "香港" | "九龍" | "新界"
        # Fallback: derive zh from code if chi.Region is absent
        if not region_zh:
            region_zh = REGION_CODE_TO_ZH.get(region_code, "")

        # ── District ──────────────────────────────────────────────────────
        # FIX 1+4: DcDistrict is the full English name, not a code
        eng_district_obj = eng.get("EngDistrict") or {}
        district_en_full = eng_district_obj.get("DcDistrict", "")
        # Strip " District" suffix for the short form used in addresses
        district_en = district_en_full.replace(" District", "").strip()

        # FIX 2: ChiDistrict.DcDistrict returns "油尖旺區" (with 區)
        chi_district_obj = chi.get("ChiDistrict") or {}
        district_zh_raw  = chi_district_obj.get("DcDistrict", "")
        # Strip trailing 區 for consistent matching (addresses use "油尖旺" not "油尖旺區")
        district_zh = district_zh_raw.rstrip("區").strip()
        # Cross-derive: if chi district missing, derive from eng name
        if not district_zh and district_en_full:
            district_zh = DISTRICT_EN_TO_ZH.get(district_en_full, "").rstrip("區")

        # ── Street (FIX 5: fall back to Village if Street absent) ─────────
        eng_street  = eng.get("EngStreet")  or {}
        chi_street  = chi.get("ChiStreet")  or {}
        eng_village = eng.get("EngVillage") or {}
        chi_village = chi.get("ChiVillage") or {}

        # FIX 7: LocationName is a place name inside EngStreet/ChiStreet
        street_en_location = eng_street.get("LocationName", "")
        street_zh_location = chi_street.get("LocationName", "")

        street_en  = (eng_street.get("StreetName") or
                      eng_village.get("VillageName") or
                      street_en_location or "").title()
        street_zh  = (chi_street.get("StreetName") or
                      chi_village.get("VillageName") or
                      street_zh_location or "")

        # Street number: prefer street, fall back to village
        no_from = (eng_street.get("BuildingNoFrom") or
                   chi_street.get("BuildingNoFrom") or
                   eng_village.get("BuildingNoFrom") or
                   chi_village.get("BuildingNoFrom") or "")
        no_to   = (eng_street.get("BuildingNoTo") or
                   chi_street.get("BuildingNoTo") or
                   eng_village.get("BuildingNoTo") or
                   chi_village.get("BuildingNoTo") or "")

        # ── Building ──────────────────────────────────────────────────────
        building_en = eng.get("BuildingName", "").title()
        building_zh = chi.get("BuildingName", "")

        # ── Estate ───────────────────────────────────────────────────────
        estate_en = (eng.get("EngEstate") or {}).get("EstateName", "").title()
        estate_zh = (chi.get("ChiEstate") or {}).get("EstateName", "")

        # ── FIX 6: Block ─────────────────────────────────────────────────
        eng_block = eng.get("EngBlock") or {}
        chi_block = chi.get("ChiBlock") or {}
        block_en  = _build_block(
            eng_block.get("BlockDescriptor", ""),
            eng_block.get("BlockNo", ""),
            eng_block.get("BlockDescriptorPrecedenceIndicator", "Y")
        )
        block_zh  = _build_block(
            chi_block.get("BlockDescriptor", ""),
            chi_block.get("BlockNo", ""),
            chi_block.get("BlockDescriptorPrecedenceIndicator", "Y")
        )

        # ── Geo ───────────────────────────────────────────────────────────
        lat = geo[0].get("Latitude",  "") if geo else ""
        lng = geo[0].get("Longitude", "") if geo else ""

        record = {
            "region_en":      region_en,
            "region_zh":      region_zh,
            "district_en":    district_en,       # "Yau Tsim Mong" (no "District")
            "district_zh":    district_zh,        # "油尖旺" (no "區")
            "street_en":      street_en,
            "street_zh":      street_zh,
            "street_no_from": str(no_from),
            "street_no_to":   str(no_to),
            "building_en":    building_en,
            "building_zh":    building_zh,
            "estate_en":      estate_en,
            "estate_zh":      estate_zh,
            "block_en":       block_en,           # NEW: "Block A" | "Tower 3"
            "block_zh":       block_zh,           # NEW: "A座" | "東座"
            "latitude":       str(lat),
            "longitude":      str(lng),
        }

        # Reject records with no usable address content
        if not any([region_zh, street_zh, building_zh]):
            return None
        return record

    # ── XML parsing (mirrors JSON fixes) ──────────────────────────────────

    def _parse_xml(self, raw: bytes) -> list:
        root    = ET.fromstring(raw.decode("utf-8"))
        records = []
        for el in root.findall(".//SuggestedAddress/Address/PremisesAddress"):
            r = self._extract_xml(el)
            if r:
                records.append(r)
        return records

    def _extract_xml(self, paddr: ET.Element) -> Optional[dict]:
        def txt(*path) -> str:
            cur = paddr
            for tag in path:
                cur = cur.find(tag)
                if cur is None:
                    return ""
            return (cur.text or "").strip()

        region_code      = txt("EngPremisesAddress", "Region")
        district_en_full = txt("EngPremisesAddress", "EngDistrict", "DcDistrict")
        district_en      = district_en_full.replace(" District", "").strip()
        district_zh_raw  = txt("ChiPremisesAddress", "ChiDistrict", "DcDistrict")
        district_zh      = district_zh_raw.rstrip("區").strip()
        if not district_zh and district_en_full:
            district_zh = DISTRICT_EN_TO_ZH.get(district_en_full, "").rstrip("區")

        street_en  = (txt("EngPremisesAddress","EngStreet","StreetName") or
                      txt("EngPremisesAddress","EngVillage","VillageName")).title()
        street_zh  = (txt("ChiPremisesAddress","ChiStreet","StreetName") or
                      txt("ChiPremisesAddress","ChiVillage","VillageName"))
        no_from    = (txt("EngPremisesAddress","EngStreet","BuildingNoFrom") or
                      txt("EngPremisesAddress","EngVillage","BuildingNoFrom"))
        no_to      = (txt("EngPremisesAddress","EngStreet","BuildingNoTo") or
                      txt("EngPremisesAddress","EngVillage","BuildingNoTo"))

        blk_desc   = txt("EngPremisesAddress","EngBlock","BlockDescriptor")
        blk_no     = txt("EngPremisesAddress","EngBlock","BlockNo")
        blk_prec   = txt("EngPremisesAddress","EngBlock","BlockDescriptorPrecedenceIndicator") or "Y"

        return {
            "region_en":      REGION_CODE_TO_EN.get(region_code, region_code),
            "region_zh":      txt("ChiPremisesAddress","Region") or REGION_CODE_TO_ZH.get(region_code,""),
            "district_en":    district_en,
            "district_zh":    district_zh,
            "street_en":      street_en,
            "street_zh":      street_zh,
            "street_no_from": no_from,
            "street_no_to":   no_to,
            "building_en":    txt("EngPremisesAddress","BuildingName").title(),
            "building_zh":    txt("ChiPremisesAddress","BuildingName"),
            "estate_en":      txt("EngPremisesAddress","EngEstate","EstateName").title(),
            "estate_zh":      txt("ChiPremisesAddress","ChiEstate","EstateName"),
            "block_en":       _build_block(blk_desc, blk_no, blk_prec),
            "block_zh":       _build_block(
                                  txt("ChiPremisesAddress","ChiBlock","BlockDescriptor"),
                                  txt("ChiPremisesAddress","ChiBlock","BlockNo"), "Y"),
            "latitude":       txt("GeospatialInformation","Latitude"),
            "longitude":      txt("GeospatialInformation","Longitude"),
        }


# ── Helpers ───────────────────────────────────────────────────────────────

def _build_block(descriptor: str, number: str, precedence: str = "Y") -> str:
    """
    Combine block descriptor + number respecting precedence indicator.
    Y = descriptor precedes number → "Block A", "座A"
    N = number precedes descriptor → "North Block", "東座"
    """
    descriptor = descriptor.strip()
    number     = number.strip()
    if not descriptor and not number:
        return ""
    if not descriptor:
        return number
    if not number:
        return descriptor
    if precedence == "Y":
        return f"{descriptor} {number}".strip()
    else:
        return f"{number} {descriptor}".strip()
