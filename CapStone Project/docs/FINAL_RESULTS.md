# ClaimGuard: measured results snapshot

Date: 2 July 2026. Hardware: NVIDIA RTX 3070 Ti (8 GB). Sentence embeddings used CPU cosine
retrieval; LoRA training and inference used CUDA 12.8 with PyTorch 2.11.0.

## Completed measurements

| Component | Dataset / run | N | Accuracy | Macro-F1 | Other result |
|---|---|---:|---:|---:|---|
| Claim-type baseline | synthetic regression set | 25 | 1.000 | 1.000 | citation-needed F1 1.000 |
| Claim-type baseline | manually annotated RQ1-RQ5 sentences | 50 | 0.520 | 0.437 | citation-needed P/R/F1 = 0.250/0.286/0.267 |
| IEEE reference parser | reference parsing benchmark | 5 | 1.000 | - | all six fields correct for all cases |
| Claim verification | five-way synthetic benchmark, lexical retrieval | 30 | 0.900 | 0.900 | micro-F1 0.900 |
| Claim verification | same benchmark, all-MiniLM-L6-v2 cosine retrieval | 30 | 0.867 | 0.868 | micro-F1 0.867 |
| SciFact LoRA training | official SciFact validation set | 450 | 0.409 | 0.353 | 1,261 train cases; 30.8 s CUDA training |
| SciFact LoRA transfer | five-way ClaimGuard benchmark | 30 | 0.300 | 0.172 | 9.1 ms mean model latency |

The embedding run is a real Sentence-Transformer run using the locally cached
`sentence-transformers/all-MiniLM-L6-v2` model. FAISS is unavailable on this Windows setup, so
normalized NumPy cosine similarity was used. On this small benchmark embeddings did not improve
the final label metrics. That negative result is retained rather than hidden.

The real-RQ annotation is a single-annotator dataset (`codex_manual_v1`), so no inter-annotator
agreement can be reported. It contains ten manually selected claim-bearing sentences from each
of the five submitted reports, with document, original sentence index, section, expected type,
citation-needed flag, and annotation rationale.

## Local versus frontier diagnostic

One cited RQ5 claim was sent successfully to each model backend. This is a connectivity and
output-difference check, not an accuracy benchmark because no gold support label was assigned.

| Backend | Model | Predicted label | Latency | Usage |
|---|---|---|---:|---|
| OpenAI | gpt-5.4-mini | insufficient_evidence | 1.889 s | 506 total tokens |
| Ollama | qwen3:1.7b | supported | 40.902 s | 388 prompt + 447 generated tokens |

The different labels and timings confirm that the two Markdown reports now represent different
model executions. A fair accuracy comparison still requires running all 30 gold benchmark cases
with each backend.

## SciFact LoRA result

The selected adapter uses `distilbert-base-uncased`, LoRA rank 8 on `q_lin`/`v_lin`, an effective
batch size of 16, seed 42, and three epochs. It trained 740,355 parameters (1.09% of the model) on
all 1,261 SciFact training pairs. Adapter, tokenizer, checkpoints, and provenance are stored in
`outputs/scifact-lora`.

The transfer score is lower because SciFact supplies three labels, whereas ClaimGuard's
benchmark additionally requires partial support and not-supported. The LoRA model cannot emit
those two labels without taxonomy adaptation.

## Implemented but not executable on this hardware

- The official Binoculars integration and isolated dependency profile are implemented. The
  calibrated Falcon-7B/Falcon-7B-Instruct pair totals about 14B parameters and cannot fit in the
  available 8 GB VRAM. No Binoculars result is claimed.

## Reproducible output files

- `outputs/rq_claim_evaluation.json`
- `outputs/reference_evaluation.json`
- `outputs/evaluation_lexical.json`
- `outputs/evaluation_embeddings.json`
- `outputs/model_comparison.json` and `outputs/model_comparison.md`
- `outputs/evaluation_lora.json`
- `outputs/scifact-lora/training_report.json` and the saved adapter
- `outputs/rq5_openai.json` and `outputs/rq5_ollama.json`

These numbers are suitable for the current report draft. A full 30-case Ollama/OpenAI run and
official Binoculars execution still require additional API budget or larger hardware.
