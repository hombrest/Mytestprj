"""
HK Address Training Data Pipeline
==================================
End-to-end pipeline:
  1. Extract      — query ALS API with seed terms, parse XML/JSON response
  2. Normalize    — unify field names, clean values, deduplicate
  3. Augment      — generate script/format variants from each canonical record
  4. Label        — produce character-level BIO labels for NER training
  5. Validate     — alignment checks, distribution report
  6. Export       — JSONL for LLM fine-tuning + NER token format

Usage:
    python pipeline.py --seeds seeds.txt --out ./output --limit 200
"""

import argparse
import json
import logging
import sys
from pathlib import Path

from extractor.als_client    import ALSClient
from processor.normalizer    import normalize_record
from processor.deduplicator  import Deduplicator
from augmentor.variants      import VariantGenerator
from augmentor.noise         import NoiseInjector
from validator.label_aligner import align_labels, validate_alignment
from validator.stats         import print_distribution_report
from exporter                import export_ner_jsonl, export_llm_jsonl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("pipeline")


def run(seeds: list[str], out_dir: Path, limit: int, n_per_query: int = 20):
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Stage 1: Extract ───────────────────────────────────────────────────
    log.info(f"Stage 1 · Extracting from ALS API ({len(seeds)} seeds, {n_per_query} results each)")
    client = ALSClient(n_results=n_per_query, delay=0.5)
    raw_records = []
    for seed in seeds:
        records = client.query(seed)
        raw_records.extend(records)
        log.info(f"  '{seed}' → {len(records)} records  (total {len(raw_records)})")

    log.info(f"Stage 1 done · {len(raw_records)} raw records")

    # ── Stage 2: Normalize + Deduplicate ───────────────────────────────────
    log.info("Stage 2 · Normalizing and deduplicating")
    normalized = [normalize_record(r) for r in raw_records]
    normalized = [r for r in normalized if r is not None]

    dedup = Deduplicator()
    canonical = dedup.run(normalized)
    log.info(f"Stage 2 done · {len(canonical)} canonical records after dedup")

    # ── Stage 3: Augment ───────────────────────────────────────────────────
    log.info("Stage 3 · Generating variants")
    gen     = VariantGenerator()
    noise   = NoiseInjector(noise_rate=0.2)  # 20% of examples get noise
    dataset = []

    for record in canonical[:limit]:
        variants = gen.generate(record)           # pure structural variants
        for v in variants:
            dataset.append(v)
            noisy = noise.inject(v)               # optionally add noise
            if noisy is not None:
                dataset.append(noisy)

    log.info(f"Stage 3 done · {len(dataset)} examples after augmentation")

    # ── Stage 4: Label ─────────────────────────────────────────────────────
    log.info("Stage 4 · Aligning BIO labels")
    labeled, skipped = [], 0
    for ex in dataset:
        labels = align_labels(ex["address"], ex["parsed"])
        errors = validate_alignment(ex["address"], labels, ex["parsed"])
        if errors:
            skipped += 1
            continue
        labeled.append({**ex, "bio_labels": labels})

    log.info(f"Stage 4 done · {len(labeled)} labeled, {skipped} skipped (alignment errors)")

    # ── Stage 5: Validate ──────────────────────────────────────────────────
    log.info("Stage 5 · Validation report")
    all_labels = [l for ex in labeled for l in ex["bio_labels"]]
    print_distribution_report(all_labels)

    # ── Stage 6: Export ────────────────────────────────────────────────────
    log.info("Stage 6 · Exporting")
    ner_path = out_dir / "ner_dataset.jsonl"
    llm_path = out_dir / "llm_finetune.jsonl"

    export_ner_jsonl(labeled, ner_path)
    export_llm_jsonl(labeled, llm_path)

    log.info(f"✓ NER dataset  → {ner_path}  ({len(labeled)} examples)")
    log.info(f"✓ LLM dataset  → {llm_path}  ({len(labeled)} examples)")
    log.info("Pipeline complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds",  default="seeds.txt",  help="One query term per line")
    parser.add_argument("--out",    default="./output",   help="Output directory")
    parser.add_argument("--limit",  type=int, default=200, help="Max canonical records to augment")
    parser.add_argument("--n",      type=int, default=20,  help="ALS results per query")
    args = parser.parse_args()

    seeds_path = Path(args.seeds)
    if not seeds_path.exists():
        # Default seeds covering all 18 districts + common building types
        default_seeds = [
            "中環", "灣仔", "銅鑼灣", "北角", "西環",         # HK Island
            "旺角", "尖沙咀", "油麻地", "深水埗", "九龍城",     # Kowloon
            "黃大仙", "觀塘", "新蒲崗",                        # East Kowloon
            "沙田", "荃灣", "屯門", "元朗", "大埔", "西貢",     # NT
            "赤鱲角機場", "青衣", "將軍澳", "天水圍",           # New towns
            "工業大廈", "屋苑", "政府大樓", "商業中心",         # Building types
            "Nathan Road", "Des Voeux Road", "Hennessy Road",  # English queries
        ]
        seeds_path.write_text("\n".join(default_seeds), encoding="utf-8")
        log.info(f"Created default seeds file at {seeds_path}")

    seeds = [s.strip() for s in seeds_path.read_text(encoding="utf-8").splitlines() if s.strip()]
    run(seeds, Path(args.out), limit=args.limit, n_per_query=args.n)
