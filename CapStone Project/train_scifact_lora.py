"""Fine-tune a scientific claim verifier on SciFact with LoRA (optional Module 5)."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path


LABEL2ID = {"SUPPORT": 0, "CONTRADICT": 1, "NOT_ENOUGH_INFO": 2}
ID2LABEL = {0: "SUPPORT", 1: "CONTRADICT", 2: "NOT_ENOUGH_INFO"}
SCIFACT_URL = "https://scifact.s3-us-west-2.amazonaws.com/release/latest/data.tar.gz"
SCIFACT_SHA256 = "11c621288d41ac144d29b13b0f8503b3820b7d6e8b1f6ff24dff335c196d76be"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a SciFact verifier with LoRA.")
    parser.add_argument("--base-model", default="microsoft/deberta-v3-base")
    parser.add_argument("--output", default="outputs/scifact-lora")
    parser.add_argument("--epochs", type=float, default=3.0)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-length", type=int, default=512)
    parser.add_argument("--lora-r", type=int, default=8)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument(
        "--target-modules",
        default="auto",
        help="auto or comma-separated module suffixes; auto detects attention Q/V projections.",
    )
    parser.add_argument("--gradient-accumulation", type=int, default=4)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--max-eval-samples", type=int)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-cache", default="data/cache/scifact-data.tar.gz")
    args = parser.parse_args()

    try:
        import numpy as np
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            DataCollatorWithPadding,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit('Install training dependencies with: python -m pip install ".[lora]"') from exc

    archive = _download_scifact_archive(Path(args.data_cache))
    corpus_rows = _read_jsonl_member(archive, "data/corpus.jsonl")
    corpus = {str(row["doc_id"]): row for row in corpus_rows}
    claim_files = {
        "train": "data/claims_train.jsonl",
        "validation": "data/claims_dev.jsonl",
    }

    def prepare(split: str) -> Dataset:
        rows: list[dict[str, object]] = []
        for row in _read_jsonl_member(archive, claim_files[split]):
            expanded = _expand_claim_row(row)
            for claim, doc_id, raw_label in expanded:
                document = corpus.get(doc_id, {})
                abstract = " ".join(document.get("abstract") or [])
                evidence = f"{document.get('title', '')}. {abstract}".strip()
                if not claim or not evidence:
                    continue
                rows.append(
                    {
                        "claim": claim,
                        "evidence": evidence,
                        "label": LABEL2ID[_normalize_label(raw_label)],
                    }
                )
        return Dataset.from_list(rows)

    train_data = prepare("train")
    validation_data = prepare("validation")
    if args.max_train_samples:
        train_data = train_data.select(range(min(args.max_train_samples, len(train_data))))
    if args.max_eval_samples:
        validation_data = validation_data.select(
            range(min(args.max_eval_samples, len(validation_data)))
        )
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)

    def tokenize(batch: dict[str, list[object]]) -> dict[str, object]:
        return tokenizer(
            batch["claim"],
            batch["evidence"],
            truncation=True,
            max_length=args.max_length,
        )

    train_data = train_data.map(tokenize, batched=True, remove_columns=["claim", "evidence"])
    validation_data = validation_data.map(tokenize, batched=True, remove_columns=["claim", "evidence"])

    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=3,
        id2label=ID2LABEL,
        label2id=LABEL2ID,
    )
    targets: str | list[str]
    if args.target_modules.strip() == "auto":
        targets = _detect_lora_targets(model)
    elif args.target_modules.strip() == "all-linear":
        targets = "all-linear"
    else:
        targets = [item.strip() for item in args.target_modules.split(",") if item.strip()]
    head_modules = _detect_head_modules(model)
    lora_config = LoraConfig(
        task_type=TaskType.SEQ_CLS,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.1,
        target_modules=targets,
        modules_to_save=list(head_modules),
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    def metrics(prediction: object) -> dict[str, float]:
        predictions = np.asarray(prediction.predictions).argmax(axis=-1)
        labels = np.asarray(prediction.label_ids)
        accuracy = float((predictions == labels).mean())
        f1_values: list[float] = []
        for label in range(3):
            tp = int(((predictions == label) & (labels == label)).sum())
            fp = int(((predictions == label) & (labels != label)).sum())
            fn = int(((predictions != label) & (labels == label)).sum())
            precision = tp / (tp + fp) if tp + fp else 0.0
            recall = tp / (tp + fn) if tp + fn else 0.0
            f1_values.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
        return {"accuracy": round(accuracy, 4), "macro_f1": round(sum(f1_values) / 3, 4)}

    output = Path(args.output)
    import torch

    using_cuda = torch.cuda.is_available()
    using_bf16 = using_cuda and torch.cuda.is_bf16_supported()
    training_kwargs = {
        "output_dir": str(output),
        "learning_rate": args.learning_rate,
        "per_device_train_batch_size": args.batch_size,
        "per_device_eval_batch_size": args.batch_size,
        "gradient_accumulation_steps": args.gradient_accumulation,
        "num_train_epochs": args.epochs,
        "weight_decay": 0.01,
        "logging_steps": 25,
        "save_strategy": "epoch",
        "save_total_limit": 2,
        "load_best_model_at_end": True,
        "metric_for_best_model": "macro_f1",
        "greater_is_better": True,
        "report_to": [],
        "seed": args.seed,
        "fp16": using_cuda and not using_bf16,
        "bf16": using_bf16,
        "use_cpu": not using_cuda,
    }
    training_signature = inspect.signature(TrainingArguments.__init__)
    evaluation_key = (
        "eval_strategy" if "eval_strategy" in training_signature.parameters else "evaluation_strategy"
    )
    training_kwargs[evaluation_key] = "epoch"
    training_args = TrainingArguments(**training_kwargs)
    trainer_kwargs = {
        "model": model,
        "args": training_args,
        "train_dataset": train_data,
        "eval_dataset": validation_data,
        "data_collator": DataCollatorWithPadding(tokenizer=tokenizer),
        "compute_metrics": metrics,
    }
    if "processing_class" in inspect.signature(Trainer.__init__).parameters:
        trainer_kwargs["processing_class"] = tokenizer
    else:
        trainer_kwargs["tokenizer"] = tokenizer
    trainer = Trainer(**trainer_kwargs)
    train_result = trainer.train()
    evaluation = trainer.evaluate()
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    report = {
        "base_model": args.base_model,
        "train_examples": len(train_data),
        "validation_examples": len(validation_data),
        "train_metrics": train_result.metrics,
        "evaluation": evaluation,
        "lora": {
            "r": args.lora_r,
            "alpha": args.lora_alpha,
            "target_modules": targets,
            "modules_to_save": head_modules,
        },
        "runtime": {
            "torch": torch.__version__,
            "device": "cuda" if using_cuda else "cpu",
            "gpu": torch.cuda.get_device_name(0) if using_cuda else None,
            "precision": "bf16" if using_bf16 else "fp16" if using_cuda else "fp32",
            "seed": args.seed,
            "effective_batch_size": args.batch_size * args.gradient_accumulation,
        },
        "license_note": "SciFact is distributed under CC BY-NC 2.0; review its terms before use.",
        "dataset": {
            "source": SCIFACT_URL,
            "archive_sha256": SCIFACT_SHA256,
            "cache": str(archive),
        },
    }
    (output / "training_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


def _normalize_label(value: str) -> str:
    normalized = value.upper().strip().replace(" ", "_")
    if normalized in {"SUPPORT", "SUPPORTS"}:
        return "SUPPORT"
    if normalized in {"CONTRADICT", "CONTRADICTS", "REFUTE", "REFUTES"}:
        return "CONTRADICT"
    return "NOT_ENOUGH_INFO"


def _download_scifact_archive(path: Path) -> Path:
    """Download the official SciFact release and verify its published checksum."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and _sha256(path) == SCIFACT_SHA256:
        return path
    partial = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(SCIFACT_URL, headers={"User-Agent": "ClaimGuard/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    checksum = _sha256(partial)
    if checksum != SCIFACT_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"SciFact archive checksum mismatch: expected {SCIFACT_SHA256}, got {checksum}"
        )
    partial.replace(path)
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl_member(archive: Path, expected_name: str) -> list[dict[str, object]]:
    """Read one known JSONL member without extracting archive paths to disk."""

    with tarfile.open(archive, "r:gz") as handle:
        member = next(
            (item for item in handle.getmembers() if item.name.replace("\\", "/") == expected_name),
            None,
        )
        if member is None or not member.isfile():
            raise RuntimeError(f"SciFact archive does not contain {expected_name}")
        stream = handle.extractfile(member)
        if stream is None:
            raise RuntimeError(f"Could not read {expected_name} from SciFact archive")
        return [json.loads(line.decode("utf-8")) for line in stream if line.strip()]


def _expand_claim_row(row: dict[str, object]) -> list[tuple[str, str, str]]:
    claim = str(row.get("claim") or "")
    evidences = row.get("evidence") or {}
    expanded: list[tuple[str, str, str]] = []
    if isinstance(evidences, dict) and evidences:
        for doc_id, groups in evidences.items():
            if not isinstance(groups, list):
                continue
            for group in groups:
                if isinstance(group, dict):
                    expanded.append((claim, str(doc_id), str(group.get("label") or "")))
        return expanded
    cited = row.get("cited_doc_ids") or []
    if isinstance(cited, list) and cited:
        expanded.append((claim, str(cited[0]), "NOT_ENOUGH_INFO"))
    return expanded


def _detect_lora_targets(model: object) -> list[str]:
    """Select attention query/value projections without touching classifier heads."""

    module_names = [name for name, _ in model.named_modules()]
    candidate_groups = [
        ["q_lin", "v_lin"],
        ["query_proj", "value_proj"],
        ["query", "value"],
        ["q_proj", "v_proj"],
    ]
    for candidates in candidate_groups:
        if all(any(name.endswith(candidate) for name in module_names) for candidate in candidates):
            return candidates
    raise RuntimeError(
        "Could not detect LoRA attention targets. Pass --target-modules with comma-separated "
        "module suffixes after inspecting model.named_modules()."
    )


def _detect_head_modules(model: object) -> list[str]:
    """Keep randomly initialized classification/pooling layers trainable and save them."""

    top_level = {name.split(".")[0] for name, _ in model.named_children()}
    candidates = ["pre_classifier", "pooler", "classifier", "score"]
    selected = [name for name in candidates if name in top_level]
    if not any(name in selected for name in ("classifier", "score")):
        raise RuntimeError("Could not detect a sequence-classification output head.")
    return selected


if __name__ == "__main__":
    main()
