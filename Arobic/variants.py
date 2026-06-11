"""
augmentor/variants.py
======================
Generates multiple address string variants from one canonical record.

Each canonical record → N example dicts:
    {"address": "...", "parsed": {...}}

Variant axes:
  - Script mode:    Chinese-only | English-only | Mixed (zh first) | Mixed (en first)
  - Ordering:       region→unit  | unit→region  (HK Post order)
  - Street number format: 100號 | No.100 | #100
  - Floor notation: (synthetic — added since ALS has no floor data)
  - Unit notation:  (synthetic)
  - Separators:     commas | spaces | newlines

ALS does NOT include floor/unit — we synthesise those to create
complete address examples. Real floor/unit data can be added if
you have a supplementary dataset (e.g. property listings).
"""

import random
import logging

log = logging.getLogger(__name__)

# ── Synthetic floor/unit pools ─────────────────────────────────────────────
FLOORS = list(range(1, 51))
UNITS  = (
    [str(i) for i in range(1, 10)] +
    [f"{f}{u}" for f in range(1,6) for u in "ABCD"] +
    [f"0{i}" for i in range(1,10)]
)

FLOOR_FMTS = [
    lambda f: f"{f}樓",
    lambda f: f"{f}/F",
    lambda f: f"{f}F",
    lambda f: f"第{f}層",
    lambda f: f"Floor {f}",
]
UNIT_FMTS = [
    lambda u: f"{u}室",
    lambda u: f"Room {u}",
    lambda u: f"Rm {u}",
    lambda u: f"Flat {u}",
    lambda u: f"Unit {u}",
    lambda u: f"Suite {u}",
]
STRNUM_FMTS = [
    lambda n: f"{n}號",
    lambda n: f"No.{n}",
    lambda n: f"No. {n}",
    lambda n: str(n),
]


class VariantGenerator:
    def generate(self, record: dict) -> list:
        variants = []
        rz = record["region"]["zh"];   re_ = record["region"]["en"]
        dz = record["district"]["zh"]; de  = record["district"]["en"]
        sz = record["street"]["zh"];   se  = record["street"]["en"]
        sn = record["street_no"]
        bz = record["building"]["zh"]; be  = record["building"]["en"]

        floor = random.choice(FLOORS)
        unit  = random.choice(UNITS)

        for _ in range(6):  # 6 variants per canonical record
            mode = random.choice(["zh_only","en_only","mixed_zh","mixed_en","hkpost_zh","hkpost_en"])
            fl_fmt = random.choice(FLOOR_FMTS)(floor)
            un_fmt = random.choice(UNIT_FMTS)(unit)
            sn_fmt = random.choice(STRNUM_FMTS)(sn) if sn else ""

            parsed = {
                "region_zh":    rz, "region_en":    re_,
                "district_zh":  dz, "district_en":  de,
                "street_zh":    sz, "street_en":    se,
                "street_no":    sn,
                "building_zh":  bz, "building_en":  be,
                "floor":        str(floor),
                "unit":         unit,
            }

            if mode == "zh_only" and rz and dz and sz:
                # 香港九龍油尖旺彌敦道100號始創中心23樓2301室
                parts = [rz, dz, sz]
                if sn_fmt: parts.append(sn_fmt)
                if bz: parts.append(bz)
                parts += [fl_fmt, un_fmt]
                address = "".join(parts)

            elif mode == "en_only" and re_ and de and se:
                # Unit 2301, 23/F, Pioneer Centre, 100 Nathan Road, YTM, KLN
                parts = []
                if un_fmt: parts.append(un_fmt)
                parts.append(fl_fmt)
                if be: parts.append(be)
                if sn and se: parts.append(f"{sn} {se}")
                elif se: parts.append(se)
                if de: parts.append(de)
                if re_: parts.append(re_)
                address = ", ".join(parts)

            elif mode == "mixed_zh" and sz and se:
                # 油尖旺 Nathan Road 100號 始創中心 23/F 2301室
                parts = []
                if dz: parts.append(dz)
                if se: parts.append(se)
                if sn_fmt: parts.append(sn_fmt)
                if bz: parts.append(bz)
                parts += [fl_fmt, un_fmt]
                address = " ".join(parts)

            elif mode == "mixed_en" and sz and re_:
                # Flat 2301, 23樓, Pioneer Centre, 彌敦道 100, Yau Tsim Mong
                parts = [un_fmt, fl_fmt]
                if be or bz: parts.append(be or bz)
                if sz: parts.append(f"{sz} {sn}" if sn else sz)
                if de or dz: parts.append(de or dz)
                address = ", ".join(parts)

            elif mode == "hkpost_zh" and sz:
                # HK Post format: unit, floor, building, street_no street, district, region
                # e.g.  2301室23樓始創中心彌敦道100號油尖旺九龍
                parts = [un_fmt, fl_fmt]
                if bz: parts.append(bz)
                if sz:
                    parts.append(sz + (sn_fmt if sn else ""))
                if dz: parts.append(dz)
                if rz: parts.append(rz)
                address = "".join(parts)

            else:  # hkpost_en or fallback
                parts = [un_fmt, fl_fmt]
                if be: parts.append(be)
                if sn and se: parts.append(f"{sn} {se}")
                elif se: parts.append(se)
                if de: parts.append(de)
                if re_: parts.append(re_)
                address = ", ".join(parts)

            address = address.strip().strip(",").strip()
            if len(address) < 5:
                continue

            variants.append({"address": address, "parsed": parsed})

        return variants
