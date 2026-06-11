"""
test_offline.py  (v2 — fixtures corrected to match real ALS JSON output)
=========================================================================
Fixture raw records now mirror what ALSClient._extract_json() actually returns
after the v2 fixes: district_en is "Yau Tsim Mong" (no "District" suffix),
district_zh is "油尖旺" (no "區" suffix), block fields present.
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

P = "✓"; F = "✗"; errors = 0

def check(label, ok, detail=""):
    global errors
    mark = P if ok else F
    msg = f"  {mark} {label}"
    if detail: msg += f": {detail}"
    print(msg)
    if not ok: errors += 1

# ── Fixtures: mirror REAL ALS JSON output after v2 extraction ─────────────
# district_en = "Yau Tsim Mong"  (NOT "YTM", NOT "Yau Tsim Mong District")
# district_zh = "油尖旺"          (NOT "油尖旺區")
# block fields present
RAW_RECORDS = [
    {   # 1. Commercial, Yau Tsim Mong — 100 Nathan Rd, The One
        "region_en": "Kowloon",        "region_zh": "九龍",
        "district_en": "Yau Tsim Mong","district_zh": "油尖旺",
        "street_en": "Nathan Road",    "street_zh": "彌敦道",
        "street_no_from": "100",       "street_no_to": "",
        "building_en": "The One",      "building_zh": "The One",
        "estate_en": "",               "estate_zh": "",
        "block_en": "",                "block_zh": "",
        "latitude": "22.2998",         "longitude": "114.1724",
    },
    {   # 2. Range street number, Wan Chai — 200-202 Hennessy Rd
        "region_en": "Hong Kong",      "region_zh": "香港",
        "district_en": "Wan Chai",     "district_zh": "灣仔",
        "street_en": "Hennessy Road",  "street_zh": "軒尼詩道",
        "street_no_from": "200",       "street_no_to": "202",
        "building_en": "Southorn Centre","building_zh": "修頓中心",
        "estate_en": "",               "estate_zh": "",
        "block_en": "",                "block_zh": "",
        "latitude": "22.2770",         "longitude": "114.1731",
    },
    {   # 3. Estate with block, Sha Tin — block descriptor "Y" precedence
        "region_en": "New Territories","region_zh": "新界",
        "district_en": "Sha Tin",      "district_zh": "沙田",
        "street_en": "Sha Tin Centre Street","street_zh": "沙田正街",
        "street_no_from": "2",         "street_no_to": "",
        "building_en": "",             "building_zh": "",
        "estate_en": "Sha Tin Centre", "estate_zh": "沙田中心",
        "block_en": "Block A",         "block_zh": "A座",
        "latitude": "22.3814",         "longitude": "114.1874",
    },
    {   # 4. Industrial, Kwun Tong
        "region_en": "Kowloon",        "region_zh": "九龍",
        "district_en": "Kwun Tong",    "district_zh": "觀塘",
        "street_en": "Hoi Yuen Road",  "street_zh": "開源道",
        "street_no_from": "55",        "street_no_to": "",
        "building_en": "Kwun Tong Industrial Centre","building_zh": "觀塘工業中心",
        "estate_en": "",               "estate_zh": "",
        "block_en": "",                "block_zh": "",
        "latitude": "22.3134",         "longitude": "114.2253",
    },
    {   # 5. Village address (NT), no street → uses VillageName
        "region_en": "New Territories","region_zh": "新界",
        "district_en": "Tai Po",       "district_zh": "大埔",
        "street_en": "Tai Po Hui",     "street_zh": "大埔滘",
        "street_no_from": "3",         "street_no_to": "",
        "building_en": "",             "building_zh": "",
        "estate_en": "",               "estate_zh": "",
        "block_en": "",                "block_zh": "",
        "latitude": "22.4112",         "longitude": "114.1903",
    },
    {   # 6. Duplicate of record 1 — dedup should remove
        "region_en": "Kowloon",        "region_zh": "九龍",
        "district_en": "Yau Tsim Mong","district_zh": "油尖旺",
        "street_en": "Nathan Road",    "street_zh": "彌敦道",
        "street_no_from": "100",       "street_no_to": "",
        "building_en": "The One",      "building_zh": "The One",
        "estate_en": "",               "estate_zh": "",
        "block_en": "",                "block_zh": "",
        "latitude": "22.2998",         "longitude": "114.1724",
    },
]

# ── Stage 1 ────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("Stage 1 · Extract  (fixture, no API call)")
print("="*55)
check("Fixture loaded", len(RAW_RECORDS) == 6)

# ── Stage 2: Normalize ─────────────────────────────────────────────────────
print("\nStage 2 · Normalize + Deduplicate")
print("="*55)
normalized = [normalize_record(r) for r in RAW_RECORDS]
normalized = [r for r in normalized if r is not None]
check("All 6 records normalize without error", len(normalized) == 6)

# Spot-check district extraction (the root-cause bug)
r1 = normalized[0]
check("district_zh correct (no 區)",     r1["district"]["zh"] == "油尖旺",      repr(r1["district"]["zh"]))
check("district_en correct (no District)",r1["district"]["en"] == "Yau Tsim Mong", repr(r1["district"]["en"]))
check("region_zh correct",               r1["region"]["zh"] == "九龍",          repr(r1["region"]["zh"]))
check("region_en correct",               r1["region"]["en"] == "Kowloon",       repr(r1["region"]["en"]))

# Range street number
r2 = normalized[1]
check("street_no range '200-202'", r2["street_no"] == "200-202", repr(r2["street_no"]))

# Estate fallback
r3 = normalized[2]
check("estate fallback building_zh = '沙田中心'", r3["building"]["zh"] == "沙田中心", repr(r3["building"]["zh"]))
check("block_en extracted = 'Block A'",           r3["block"]["en"] == "Block A",    repr(r3["block"]["en"]))
check("block_zh extracted = 'A座'",               r3["block"]["zh"] == "A座",        repr(r3["block"]["zh"]))

# Village record
r5 = normalized[4]
check("village street_zh = '大埔滘'", r5["street"]["zh"] == "大埔滘", repr(r5["street"]["zh"]))

# Dedup
dedup = Deduplicator()
canonical = dedup.run(normalized)
check("Dedup: 6→5 records (1 duplicate removed)", len(canonical) == 5)

# ── Stage 3: Augment ──────────────────────────────────────────────────────
print("\nStage 3 · Augment")
print("="*55)
gen   = VariantGenerator()
noise = NoiseInjector(noise_rate=1.0)
dataset = []
for record in canonical:
    for v in gen.generate(record):
        dataset.append(v)
        noisy = noise.inject(v)
        if noisy: dataset.append(noisy)

check("Generated ≥ 5×6 examples", len(dataset) >= 30, str(len(dataset)))

# ── Stage 4: Label ─────────────────────────────────────────────────────────
print("\nStage 4 · Label Alignment")
print("="*55)

# Test A: pure Chinese
addr_a  = "九龍油尖旺彌敦道100號The One"
parsed_a = {"region_zh":"九龍","region_en":"Kowloon","district_zh":"油尖旺",
            "district_en":"Yau Tsim Mong","street_zh":"彌敦道","street_en":"Nathan Road",
            "street_no":"100","building_zh":"The One","building_en":"The One","floor":"23","unit":"A"}
labs_a = align_labels(addr_a, parsed_a)
errs_a = validate_alignment(addr_a, labs_a, parsed_a)
check("Pure-Chinese alignment", not errs_a, "; ".join(errs_a) if errs_a else "ok")

# Test B: English-first with range street number
addr_b  = "Flat B, 18/F, Southorn Centre, 200-202 Hennessy Road, Wan Chai"
parsed_b = {"region_zh":"香港","region_en":"Hong Kong","district_zh":"灣仔",
            "district_en":"Wan Chai","street_zh":"軒尼詩道","street_en":"Hennessy Road",
            "street_no":"200-202","building_zh":"修頓中心","building_en":"Southorn Centre",
            "floor":"18","unit":"B"}
labs_b = align_labels(addr_b, parsed_b)
errs_b = validate_alignment(addr_b, labs_b, parsed_b)
check("English-first + range street_no alignment", not errs_b, "; ".join(errs_b) if errs_b else "ok")

# Test C: Estate + block
addr_c  = "新界沙田沙田正街2號沙田中心Block A"
parsed_c = {"region_zh":"新界","region_en":"New Territories","district_zh":"沙田",
            "district_en":"Sha Tin","street_zh":"沙田正街","street_en":"Sha Tin Centre Street",
            "street_no":"2","building_zh":"沙田中心","building_en":"Sha Tin Centre",
            "floor":"5","unit":"C"}
labs_c = align_labels(addr_c, parsed_c)
errs_c = validate_alignment(addr_c, labs_c, parsed_c)
check("Estate+block alignment", not errs_c, "; ".join(errs_c) if errs_c else "ok")

print("\n  Visualizing Test A:")
visualize(addr_a, labs_a)

# ── Stage 5: Distribution ──────────────────────────────────────────────────
print("Stage 5 · Distribution")
print("="*55)
labeled = []
for ex in dataset:
    lbs  = align_labels(ex["address"], ex["parsed"])
    errs = validate_alignment(ex["address"], lbs, ex["parsed"])
    if not errs:
        labeled.append({**ex, "bio_labels": lbs})
check(f"Labeled examples ({len(labeled)}/{len(dataset)} passed validation)",
      len(labeled) > 0)
all_labels = [l for ex in labeled for l in ex["bio_labels"]]
print_distribution_report(all_labels)

# ── Stage 6: Export ────────────────────────────────────────────────────────
print("Stage 6 · Export")
print("="*55)
out = Path("/home/claude/hk_address_pipeline/output_test")
out.mkdir(exist_ok=True)
export_ner_jsonl(labeled, out/"ner_dataset.jsonl")
export_llm_jsonl(labeled, out/"llm_finetune.jsonl")

with open(out/"ner_dataset.jsonl") as f:
    first_ner = json.loads(f.readline())
check("NER: tokens/labels same length",
      len(first_ner["tokens"]) == len(first_ner["labels"]))

with open(out/"llm_finetune.jsonl") as f:
    first_llm = json.loads(f.readline())
check("LLM: all 3 keys present",
      all(k in first_llm for k in ["instruction","input","output"]))

# ── Final ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
status = "ALL TESTS PASSED ✓" if errors == 0 else f"{errors} TEST(S) FAILED ✗"
print(f"  {status}")
print("="*55 + "\n")
