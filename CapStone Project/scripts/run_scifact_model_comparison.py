"""Compare SciFact LoRA, local zero-shot prompting, and a majority baseline."""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from claimguard.config import load_environment
from scripts.train_scifact_lora import (
    ID2LABEL,
    LABEL2ID,
    _expand_claim_row,
    _normalize_label,
    _read_jsonl_member,
)

LABELS = ("SUPPORT", "CONTRADICT", "NOT_ENOUGH_INFO")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", default="data/cache/scifact-data.tar.gz")
    parser.add_argument("--adapter", default="outputs/models/scifact-lora")
    parser.add_argument("--ollama-model", default=None)
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument("--per-label", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", required=True)
    parser.add_argument("--retries", type=int, default=2)
    args = parser.parse_args()
    load_environment()

    import os

    model = args.ollama_model or os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
    url = (args.ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
    examples = load_balanced_scifact_examples(
        Path(args.archive), per_label=args.per_label, seed=args.seed
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    predictions = _load_checkpoint(output, examples, args.adapter, model)

    if "majority" not in predictions:
        majority_label = Counter(item["expected"] for item in examples).most_common(1)[0][0]
        predictions["majority"] = [
            _prediction(item, majority_label, 0.0, "Most frequent label in the evaluation set.")
            for item in examples
        ]
        _write_checkpoint(output, examples, predictions, args.adapter, model)

    if "lora" not in predictions or len(predictions["lora"]) < len(examples):
        predictions["lora"] = _predict_lora(examples, args.adapter)
        _write_checkpoint(output, examples, predictions, args.adapter, model)

    ollama_by_id = {item["case_id"]: item for item in predictions.get("ollama_zero_shot", [])}
    for example in examples:
        if example["case_id"] in ollama_by_id:
            continue
        last_error = ""
        verdict = None
        for attempt in range(max(0, args.retries) + 1):
            try:
                verdict = _predict_ollama(example, model, url)
                break
            except Exception as exc:  # network/local service dependent
                last_error = str(exc)
                if attempt < max(0, args.retries):
                    time.sleep(2**attempt)
        if verdict is None:
            predictions["ollama_zero_shot"] = list(ollama_by_id.values())
            _write_checkpoint(output, examples, predictions, args.adapter, model, last_error)
            raise RuntimeError(
                f"Ollama failed at {example['case_id']}; rerun to resume: {last_error}"
            )
        ollama_by_id[example["case_id"]] = verdict
        predictions["ollama_zero_shot"] = [
            ollama_by_id[item["case_id"]]
            for item in examples
            if item["case_id"] in ollama_by_id
        ]
        _write_checkpoint(output, examples, predictions, args.adapter, model)

    report = _build_report(examples, predictions, args.adapter, model, complete=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def load_balanced_scifact_examples(
    archive: Path,
    per_label: int,
    seed: int,
) -> list[dict[str, str]]:
    """Load a deterministic class-balanced subset of SciFact dev pairs."""

    corpus_rows = _read_jsonl_member(archive, "data/corpus.jsonl")
    corpus = {str(row["doc_id"]): row for row in corpus_rows}
    claim_rows = _read_jsonl_member(archive, "data/claims_dev.jsonl")
    grouped: dict[str, list[dict[str, str]]] = {label: [] for label in LABELS}
    row_index = 0
    for claim_row in claim_rows:
        for claim, doc_id, raw_label in _expand_claim_row(claim_row):
            document = corpus.get(doc_id, {})
            abstract = " ".join(document.get("abstract") or [])
            evidence = f"{document.get('title', '')}. {abstract}".strip()
            if not claim or not evidence:
                continue
            label = _normalize_label(raw_label)
            row_index += 1
            grouped[label].append(
                {
                    "case_id": f"SF-{row_index:03d}",
                    "claim": claim,
                    "evidence": evidence,
                    "expected": label,
                    "doc_id": doc_id,
                }
            )
    rng = random.Random(seed)
    selected: list[dict[str, str]] = []
    for label in LABELS:
        candidates = list(grouped[label])
        rng.shuffle(candidates)
        if len(candidates) < per_label:
            raise ValueError(f"SciFact has only {len(candidates)} {label} cases")
        selected.extend(candidates[:per_label])
    rng.shuffle(selected)
    return selected


def _predict_lora(examples: list[dict[str, str]], adapter: str) -> list[dict[str, Any]]:
    import torch
    from peft import AutoPeftModelForSequenceClassification
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(adapter, local_files_only=True)
    model = AutoPeftModelForSequenceClassification.from_pretrained(
        adapter,
        local_files_only=True,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    rows: list[dict[str, Any]] = []
    for example in examples:
        started = time.perf_counter()
        encoded = tokenizer(
            example["claim"],
            example["evidence"],
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.no_grad():
            probabilities = torch.softmax(model(**encoded).logits[0], dim=-1)
        index = int(probabilities.argmax().item())
        rows.append(
            _prediction(
                example,
                ID2LABEL[index],
                (time.perf_counter() - started) * 1000,
                "SciFact-trained DistilBERT LoRA adapter.",
                confidence=float(probabilities[index].item()),
            )
        )
    return rows


def _predict_ollama(example: dict[str, str], model: str, base_url: str) -> dict[str, Any]:
    started = time.perf_counter()
    schema = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "enum": list(LABELS)},
            "rationale": {"type": "string"},
        },
        "required": ["label", "rationale"],
        "additionalProperties": False,
    }
    prompt = (
        "Classify the relationship between the CLAIM and EVIDENCE using exactly one label. "
        "SUPPORT means the evidence establishes the claim. CONTRADICT means it establishes "
        "the opposite. NOT_ENOUGH_INFO means it neither establishes nor refutes the claim. "
        "Judge only from the evidence and return the requested JSON.\n\n"
        f"CLAIM:\n{example['claim']}\n\nEVIDENCE:\n{example['evidence']}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "format": schema,
        "stream": False,
        "options": {"temperature": 0},
    }
    request = Request(
        f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "ClaimGuard/0.2"},
        method="POST",
    )
    with urlopen(request, timeout=180) as response:  # nosec - configured local Ollama endpoint
        result = json.loads(response.read().decode("utf-8"))
    parsed = json.loads(str(result.get("response") or "{}"))
    label = str(parsed.get("label") or "").upper()
    if label not in LABELS:
        raise ValueError(f"Ollama returned unsupported label {label!r}")
    return _prediction(
        example,
        label,
        (time.perf_counter() - started) * 1000,
        str(parsed.get("rationale") or "No rationale returned."),
        metadata={
            "prompt_eval_count": result.get("prompt_eval_count"),
            "eval_count": result.get("eval_count"),
        },
    )


def _prediction(
    example: dict[str, str],
    predicted: str,
    latency_ms: float,
    rationale: str,
    confidence: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": example["case_id"],
        "expected": example["expected"],
        "predicted": predicted,
        "correct": predicted == example["expected"],
        "confidence": round(confidence, 4) if confidence is not None else None,
        "latency_ms": round(latency_ms, 1),
        "rationale": rationale,
        "metadata": metadata or {},
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    per_label: dict[str, dict[str, Any]] = {}
    for label in LABELS:
        tp = sum(row["expected"] == label and row["predicted"] == label for row in rows)
        fp = sum(row["expected"] != label and row["predicted"] == label for row in rows)
        fn = sum(row["expected"] == label and row["predicted"] != label for row in rows)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": sum(row["expected"] == label for row in rows),
        }
    return {
        "n": len(rows),
        "accuracy": round(sum(row["correct"] for row in rows) / len(rows), 3) if rows else 0.0,
        "macro_f1": round(sum(item["f1"] for item in per_label.values()) / len(LABELS), 3),
        "per_label": per_label,
        "mean_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 1)
        if rows
        else 0.0,
    }


def _build_report(
    examples: list[dict[str, str]],
    predictions: dict[str, list[dict[str, Any]]],
    adapter: str,
    ollama_model: str,
    complete: bool,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "status": "complete" if complete else "in_progress",
        "dataset": "SciFact dev claim-document pairs",
        "sampling": {
            "total": len(examples),
            "per_label": dict(Counter(item["expected"] for item in examples)),
            "case_ids": [item["case_id"] for item in examples],
        },
        "models": {"lora": adapter, "ollama_zero_shot": ollama_model},
        "metrics": {name: _metrics(rows) for name, rows in predictions.items()},
        "predictions": predictions,
        "last_error": error,
        "limitations": [
            "The 90-case subset is deterministic and balanced but smaller than the 450-pair dev set.",
            "SciFact labels concern evidence relations and are directly aligned across these backends.",
            "Ollama latency depends on local hardware and warm-up state.",
        ],
    }


def _write_checkpoint(
    output: Path,
    examples: list[dict[str, str]],
    predictions: dict[str, list[dict[str, Any]]],
    adapter: str,
    ollama_model: str,
    error: str | None = None,
) -> None:
    output.write_text(
        json.dumps(
            _build_report(examples, predictions, adapter, ollama_model, False, error),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _load_checkpoint(
    output: Path,
    examples: list[dict[str, str]],
    adapter: str,
    ollama_model: str,
) -> dict[str, list[dict[str, Any]]]:
    if not output.exists():
        return {}
    payload = json.loads(output.read_text(encoding="utf-8"))
    if payload.get("sampling", {}).get("case_ids") != [item["case_id"] for item in examples]:
        raise ValueError("Existing checkpoint uses a different SciFact sample")
    if payload.get("models") != {"lora": adapter, "ollama_zero_shot": ollama_model}:
        raise ValueError("Existing checkpoint uses different models")
    return {key: list(value) for key, value in payload.get("predictions", {}).items()}


if __name__ == "__main__":
    main()
