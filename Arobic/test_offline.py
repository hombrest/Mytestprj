"""
test_offline.py
================
Tests all pipeline stages WITHOUT hitting the ALS API.
Uses a fixture of realistic records that mirror real ALS JSON output.
Run: python test_offline.py
"""

import sys, json
sys.path.insert(0, "/home/claude/hk_address_pipeline")

from processor.normalizer    import normalize_record
from processor.deduplicator  import Deduplicator
from augmentor.variants      import VariantGenerator
from augmentor.noise         import NoiseInjector
from validator.label_aligner import align_labels, validate_alignment, visualize, LABELS
from validator.stats         import print_distribution_report
from exporter                import export_ner_jsonl, export_llm_jsonl
from pathlib import Path

PASS = "✓"; FAIL = "✗"

# ── Fixture: simulated ALS raw records ────────────────────────────────────
# These mirror what ALSClient._extract_json() returns for real queries.
RAW_RECORDS = [
    {   # 1. Commercial building, Yau Tsim Mong
        "region_en": "Kowloon",     "region_zh": "九龍",
        "district_code": "YTM",    "district_en": "Yau Tsim Mong", "district_zh": "油尖旺",
        "street_en": "Nathan Road", "street_zh": "彌敦道",
        "street_no_from": "100",    "street_no_to": "",
        "building_en": "The One",   "building_zh": "The One",
        "estate_en": "",            "estate_zh": "",
        "latitude": "22.2998",      "longitude": "114.1724",
    },
    {   # 2. Range street number, Wan Chai
        "region_en": "Hong Kong",   "region_zh": "香港",
        "district_code": "WC",     "district_en": "Wan Chai", "district_zh": "灣仔",
        "street_en": "Hennessy Road", "street_zh": "軒尼詩道",
        "street_no_from": "200",    "street_no_to": "202",
        "building_en": "Southorn Centre", "building_zh": "修頓中心",
        "estate_en": "",            "estate_zh": "",
        "latitude": "22.2770",      "longitude": "114.1731",
    },
    {   # 3. Estate record, Sha Tin (uses estate not building)
        "region_en": "New Territories", "region_zh": "新界",
        "district_code": "ST",     "district_en": "Sha Tin", "district_zh": "沙田",
        "street_en": "Sha Tin Centre Street", "street_zh": "沙田正街",
        "street_no_from": "2",      "street_no_to": "",
        "building_en": "",          "building_zh": "",
        "estate_en": "Sha Tin Centre", "estate_zh": "沙田中心",
        "latitude": "22.3814",      "longitude": "114.1874",
    },
    {   # 4. Industrial building, Kwun Tong
        "region_en": "Kowloon",     "region_zh": "九龍",
        "district_code": "KT",     "district_en": "Kwun Tong", "district_zh": "觀塘",
        "street_en": "Hoi Yuen Road","street_zh": "開源道",
        "street_no_from": "55",     "street_no_to": "",
        "building_en": "Kwun Tong Industrial Centre", "building_zh": "觀塘工業中心",
        "estate_en": "",            "estate_zh": "",
        "latitude": "22.3134",      "longitude": "114.2253",
    },
    {   # 5. Duplicate of record 1 — should be removed by deduplicator
        "region_en": "Kowloon",     "region_zh": "九龍",
        "district_code": "YTM",    "district_en": "Yau Tsim Mong", "district_zh": "油尖旺",
        "street_en": "Nathan Road", "street_zh": "彌敦道",
        "street_no_from": "100",    "street_no_to": "",
        "building_en": "The One",   "building_zh": "The One",
        "estate_en": "",            "estate_zh": "",
        "latitude": "22.2998",      "longitude": "114.1724",
    },
]

errors_total = 0

# ── Stage 1 mock: use fixture instead of API ──────────────────────────────
print("\n" + "="*55)
print("Stage 1 · Extract  (fixture, no API call)")
print("="*55)
print(f"  {PASS} {len(RAW_RECORDS)} raw records loaded from fixture")

# ── Stage 2: Normalize ────────────────────────────────────────────────────
print("\nStage 2 · Normalize + Deduplicate")
print("="*55)
normalized = [normalize_record(r) for r in RAW_RECORDS]
normalized = [r for r in normalized if r is not None]
print(f"  {PASS} Normalized: {len(normalized)}/{len(RAW_RECORDS)} records kept")

dedup = Deduplicator()
canonical = dedup.run(normalized)
expected_after_dedup = 4
ok = len(canonical) == expected_after_dedup
print(f"  {PASS if ok else FAIL} Dedup: {len(canonical)} records (expected {expected_after_dedup})")
if not ok: errors_total += 1

# Spot-check range street number
st_no = canonical[1]["street_no"]
ok = st_no == "200-202"
print(f"  {PASS if ok else FAIL} Range street_no: '{st_no}' (expected '200-202')")
if not ok: errors_total += 1

# Check estate fallback
bldg = canonical[2]["building"]["zh"]
ok = bldg == "沙田中心"
print(f"  {PASS if ok else FAIL} Estate fallback building_zh: '{bldg}'")
if not ok: errors_total += 1

# ── Stage 3: Augment ─────────────────────────────────────────────────────
print("\nStage 3 · Augment")
print("="*55)
gen   = VariantGenerator()
noise = NoiseInjector(noise_rate=1.0)  # 100% noise for testing
dataset = []
for record in canonical:
    variants = gen.generate(record)
    for v in variants:
        dataset.append(v)
        noisy = noise.inject(v)
        if noisy:
            dataset.append(noisy)

print(f"  {PASS} Generated {len(dataset)} examples from {len(canonical)} canonical records")
ok = len(dataset) >= len(canonical) * 6
print(f"  {PASS if ok else FAIL} Variant count ≥ 6× canonical")
if not ok: errors_total += 1

# ── Stage 4: Label alignment ──────────────────────────────────────────────
print("\nStage 4 · Label Alignment")
print("="*55)

# Test case 1: Pure Chinese
addr1   = "九龍油尖旺彌敦道100號The One"
parsed1 = {"region_zh":"九龍","region_en":"Kowloon","district_zh":"油尖旺",
           "district_en":"Yau Tsim Mong","street_zh":"彌敦道","street_en":"Nathan Road",
           "street_no":"100","building_zh":"The One","building_en":"The One",
           "floor":"18","unit":"A"}
labels1 = align_labels(addr1, parsed1)
errs1   = validate_alignment(addr1, labels1, parsed1)
ok = not errs1
print(f"  {PASS if ok else FAIL} Pure-Chinese alignment: {addr1}")
if not ok:
    for e in errs1: print(f"      ERROR: {e}")
    errors_total += 1

# Test case 2: English-first
addr2   = "Flat A, 18/F, Southorn Centre, 200-202 Hennessy Road, Wan Chai"
parsed2 = {"region_zh":"香港","region_en":"Hong Kong","district_zh":"灣仔",
           "district_en":"Wan Chai","street_zh":"軒尼詩道","street_en":"Hennessy Road",
           "street_no":"200-202","building_zh":"修頓中心","building_en":"Southorn Centre",
           "floor":"18","unit":"A"}
labels2 = align_labels(addr2, parsed2)
errs2   = validate_alignment(addr2, labels2, parsed2)
ok = not errs2
print(f"  {PASS if ok else FAIL} English-first alignment: {addr2[:40]}...")
if not ok:
    for e in errs2: print(f"      ERROR: {e}")
    errors_total += 1

# Test case 3: Detailed visualization
print("\n  Detailed label visualization (test case 1):")
visualize(addr1, labels1)

# ── Stage 5: Distribution ─────────────────────────────────────────────────
print("Stage 5 · Distribution Report")
labeled = []
for ex in dataset:
    lbs = align_labels(ex["address"], ex["parsed"])
    errs = validate_alignment(ex["address"], lbs, ex["parsed"])
    if not errs:
        labeled.append({**ex, "bio_labels": lbs})

all_labels = [l for ex in labeled for l in ex["bio_labels"]]
print_distribution_report(all_labels)

# ── Stage 6: Export ───────────────────────────────────────────────────────
print("Stage 6 · Export")
print("="*55)
out = Path("/home/claude/hk_address_pipeline/output_test")
out.mkdir(exist_ok=True)
export_ner_jsonl(labeled, out / "ner_dataset.jsonl")
export_llm_jsonl(labeled, out / "llm_finetune.jsonl")

# Spot-check exported NER file
with open(out / "ner_dataset.jsonl") as f:
    first = json.loads(f.readline())
ok = "tokens" in first and "labels" in first and len(first["tokens"]) == len(first["labels"])
print(f"  {PASS if ok else FAIL} NER JSONL: tokens/labels aligned")
if not ok: errors_total += 1

with open(out / "llm_finetune.jsonl") as f:
    first_llm = json.loads(f.readline())
ok = "instruction" in first_llm and "input" in first_llm and "output" in first_llm
print(f"  {PASS if ok else FAIL} LLM JSONL: instruction/input/output keys present")
if not ok: errors_total += 1

# ── Summary ────────────────────────────────────────────────────────────────
print("\n" + "="*55)
if errors_total == 0:
    print(f"  ALL TESTS PASSED  ({PASS})")
else:
    print(f"  {errors_total} TEST(S) FAILED  ({FAIL})")
print("="*55 + "\n")
