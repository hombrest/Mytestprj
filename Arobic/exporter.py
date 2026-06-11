"""
exporter.py
============
Writes the final labeled dataset in two formats:

1. NER JSONL (for the from-scratch transformer NER model)
   One JSON object per line:
   {
     "tokens":  ["九","龍","旺","角",...],
     "labels":  ["B-REGION","I-REGION","B-DISTRICT","I-DISTRICT",...],
     "address": "九龍旺角...",
     "parsed":  {...}
   }

2. LLM JSONL (for QLoRA fine-tuning, instruction format)
   {
     "instruction": "Parse the following Hong Kong address...",
     "input":       "九龍旺角彌敦道100號始創中心23樓2301室",
     "output":      "{...}"   ← JSON string of parsed fields
   }
"""

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)


def export_ner_jsonl(labeled: list, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        for ex in labeled:
            record = {
                "tokens":  list(ex["address"]),      # character-level tokens
                "labels":  ex["bio_labels"],
                "address": ex["address"],
                "parsed":  ex["parsed"],
            }
            if ex.get("_noisy"):
                record["_noisy"] = True
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info(f"Wrote {len(labeled)} NER examples → {path}")


def export_llm_jsonl(labeled: list, path: Path):
    INSTRUCTION = (
        "Parse the following Hong Kong address into its structural components. "
        "Return a JSON object with keys: region_zh, region_en, district_zh, district_en, "
        "street_zh, street_en, street_no, building_zh, building_en, floor, unit. "
        "Leave fields empty string if not present in the address."
    )
    with open(path, "w", encoding="utf-8") as f:
        for ex in labeled:
            record = {
                "instruction": INSTRUCTION,
                "input":       ex["address"],
                "output":      json.dumps(ex["parsed"], ensure_ascii=False),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    log.info(f"Wrote {len(labeled)} LLM examples → {path}")
