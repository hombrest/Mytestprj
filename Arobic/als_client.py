"""
extractor/als_client.py
========================
Queries the HK Government Address Lookup Service (ALS).
API: https://www.als.gov.hk/lookup
Docs: https://www.als.gov.hk/docs/Data_Dictionary_for_ALS_EN-v3.2.pdf

ALS JSON response structure:
{
  "SuggestedAddress": [{
    "Address": {
      "PremisesAddress": {
        "ChiPremisesAddress": {
          "Region": "九龍",
          "ChiDistrict": {"DcDistrict": "YTM"},
          "ChiStreet":   {"StreetName": "彌敦道", "BuildingNoFrom": "100"},
          "BuildingName": "始創中心",
          "ChiEstate":   {"EstateName": "..."}
        },
        "EngPremisesAddress": {
          "Region": "KLN",
          "EngDistrict": {"DcDistrict": "YTM"},
          "EngStreet":   {"StreetName": "NATHAN ROAD", "BuildingNoFrom": "100"},
          "BuildingName": "PIONEER CENTRE"
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

DISTRICT_CODE_MAP = {
    "CW":  {"zh": "中西區",  "en": "Central & Western"},
    "WC":  {"zh": "灣仔",    "en": "Wan Chai"},
    "EST": {"zh": "東區",    "en": "Eastern"},
    "SO":  {"zh": "南區",    "en": "Southern"},
    "YTM": {"zh": "油尖旺",  "en": "Yau Tsim Mong"},
    "SSP": {"zh": "深水埗",  "en": "Sham Shui Po"},
    "KC":  {"zh": "九龍城",  "en": "Kowloon City"},
    "WTS": {"zh": "黃大仙",  "en": "Wong Tai Sin"},
    "KT":  {"zh": "觀塘",    "en": "Kwun Tong"},
    "TW":  {"zh": "荃灣",    "en": "Tsuen Wan"},
    "TM":  {"zh": "屯門",    "en": "Tuen Mun"},
    "YL":  {"zh": "元朗",    "en": "Yuen Long"},
    "N":   {"zh": "北區",    "en": "North"},
    "TP":  {"zh": "大埔",    "en": "Tai Po"},
    "ST":  {"zh": "沙田",    "en": "Sha Tin"},
    "SK":  {"zh": "西貢",    "en": "Sai Kung"},
    "I":   {"zh": "離島",    "en": "Islands"},
    "KI":  {"zh": "葵青",    "en": "Kwai Tsing"},
}
REGION_MAP = {
    "HK":  {"zh": "香港",  "en": "Hong Kong"},
    "KLN": {"zh": "九龍",  "en": "Kowloon"},
    "NT":  {"zh": "新界",  "en": "New Territories"},
}


class ALSClient:
    def __init__(self, n_results=20, delay=0.5, use_json=True):
        self.n_results = n_results
        self.delay = delay
        self.use_json = use_json

    def query(self, term: str) -> list:
        url = f"{ALS_BASE}?{urllib.parse.urlencode({'q': term, 'n': self.n_results})}"
        req = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "Accept-Language": "zh-Hant,en",
            "User-Agent": "HKAddressPipeline/1.0 (research)",
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

    def _parse_json(self, raw: bytes) -> list:
        data = json.loads(raw.decode("utf-8"))
        records = []
        for item in data.get("SuggestedAddress", []):
            try:
                paddr = item["Address"]["PremisesAddress"]
                r = self._extract_json(paddr)
                if r: records.append(r)
            except (KeyError, TypeError):
                continue
        return records

    def _extract_json(self, paddr: dict) -> Optional[dict]:
        eng = paddr.get("EngPremisesAddress", {})
        chi = paddr.get("ChiPremisesAddress", {})
        geo = paddr.get("GeospatialInformation", [{}])
        if isinstance(geo, dict): geo = [geo]
        region_code   = eng.get("Region", "")
        district_code = (eng.get("EngDistrict") or {}).get("DcDistrict", "")
        es = eng.get("EngStreet") or {}
        cs = chi.get("ChiStreet") or {}
        r = {
            "region_en":      REGION_MAP.get(region_code, {}).get("en", region_code),
            "region_zh":      REGION_MAP.get(region_code, {}).get("zh", chi.get("Region", "")),
            "district_code":  district_code,
            "district_en":    DISTRICT_CODE_MAP.get(district_code, {}).get("en", district_code),
            "district_zh":    DISTRICT_CODE_MAP.get(district_code, {}).get("zh", ""),
            "street_en":      es.get("StreetName", "").title(),
            "street_zh":      cs.get("StreetName", ""),
            "street_no_from": str(es.get("BuildingNoFrom") or cs.get("BuildingNoFrom") or ""),
            "street_no_to":   str(es.get("BuildingNoTo")   or cs.get("BuildingNoTo")   or ""),
            "building_en":    eng.get("BuildingName", "").title(),
            "building_zh":    chi.get("BuildingName", ""),
            "estate_en":      (eng.get("EngEstate") or {}).get("EstateName", "").title(),
            "estate_zh":      (chi.get("ChiEstate") or {}).get("EstateName", ""),
            "latitude":       geo[0].get("Latitude", "") if geo else "",
            "longitude":      geo[0].get("Longitude", "") if geo else "",
        }
        return r if any([r["street_zh"], r["street_en"], r["building_zh"]]) else None

    def _parse_xml(self, raw: bytes) -> list:
        root = ET.fromstring(raw.decode("utf-8"))
        records = []
        for el in root.findall(".//SuggestedAddress/Address/PremisesAddress"):
            def t(*path):
                cur = el
                for tag in path:
                    cur = cur.find(tag)
                    if cur is None: return ""
                return (cur.text or "").strip()
            rc = t("EngPremisesAddress","Region")
            dc = t("EngPremisesAddress","EngDistrict","DcDistrict")
            records.append({
                "region_en": REGION_MAP.get(rc,{}).get("en",rc),
                "region_zh": REGION_MAP.get(rc,{}).get("zh",""),
                "district_code": dc,
                "district_en": DISTRICT_CODE_MAP.get(dc,{}).get("en",dc),
                "district_zh": DISTRICT_CODE_MAP.get(dc,{}).get("zh",""),
                "street_en":      t("EngPremisesAddress","EngStreet","StreetName").title(),
                "street_zh":      t("ChiPremisesAddress","ChiStreet","StreetName"),
                "street_no_from": t("EngPremisesAddress","EngStreet","BuildingNoFrom"),
                "street_no_to":   t("EngPremisesAddress","EngStreet","BuildingNoTo"),
                "building_en":    t("EngPremisesAddress","BuildingName").title(),
                "building_zh":    t("ChiPremisesAddress","BuildingName"),
                "estate_en":      t("EngPremisesAddress","EngEstate","EstateName").title(),
                "estate_zh":      t("ChiPremisesAddress","ChiEstate","EstateName"),
                "latitude":       t("GeospatialInformation","Latitude"),
                "longitude":      t("GeospatialInformation","Longitude"),
            })
        return records
