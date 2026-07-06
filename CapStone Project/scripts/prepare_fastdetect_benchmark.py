"""Create a balanced AI-detection benchmark from official Fast-DetectGPT data."""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Official *.raw_data.json file")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pairs", type=int, default=15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minimum-words", type=int, default=40)
    args = parser.parse_args()

    source = Path(args.input)
    payload = json.loads(source.read_text(encoding="utf-8"))
    originals = list(payload.get("original") or [])
    samples = list(payload.get("sampled") or [])
    eligible = [
        index
        for index, (original, sample) in enumerate(zip(originals, samples))
        if len(str(original).split()) >= args.minimum_words
        and len(str(sample).split()) >= args.minimum_words
    ]
    if len(eligible) < args.pairs:
        raise ValueError(f"Only {len(eligible)} paired examples satisfy the length threshold")
    selected = random.Random(args.seed).sample(eligible, args.pairs)
    rows: list[dict[str, object]] = []
    for index in selected:
        provenance = f"official-fast-detect-gpt:{source.name}:pair-{index}"
        rows.extend(
            [
                {
                    "case_id": f"FD-{index:03d}-H",
                    "text": originals[index],
                    "expected_label": "human",
                    "citation_count": 0,
                    "source": provenance,
                },
                {
                    "case_id": f"FD-{index:03d}-A",
                    "text": samples[index],
                    "expected_label": "ai",
                    "citation_count": 0,
                    "source": provenance,
                },
            ]
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["case_id", "text", "expected_label", "citation_count", "source"],
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
