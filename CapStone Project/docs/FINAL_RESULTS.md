# ClaimGuard: measured results snapshot

Date: 6 July 2026. Hardware: NVIDIA RTX 3070 Ti (8 GB). Sentence embeddings used CPU cosine
retrieval; LoRA training and inference used CUDA 12.8 with PyTorch 2.11.0.

## Completed measurements

| Component | Dataset / run | N | Accuracy | Macro-F1 | Other result |
|---|---|---:|---:|---:|---|
| Claim-type baseline | synthetic regression set | 25 | 1.000 | 1.000 | citation-needed F1 1.000 |
| Claim-type baseline | manually annotated RQ1-RQ5 sentences | 50 | 0.520 | 0.437 | citation-needed P/R/F1 = 0.250/0.286/0.267 |
| IEEE reference parser | reference parsing benchmark | 5 | 1.000 | - | all six fields correct for all cases |
| Bibliographic status | 20 authentic + 10 controlled references | 30 | 0.467 | 0.412 | DOI F1 1.000 (N=7); retraction F1 0.667 |
| Claim verification | five-way synthetic benchmark, lexical retrieval | 30 | 0.900 | 0.900 | micro-F1 0.900 |
| Claim verification | same benchmark, all-MiniLM-L6-v2 cosine retrieval | 30 | 0.867 | 0.868 | micro-F1 0.867 |
| SciFact LoRA training | official SciFact validation set | 450 | 0.409 | 0.353 | 1,261 train cases; 30.8 s CUDA training |
| Majority baseline | balanced SciFact subset | 90 | 0.333 | 0.167 | 30 cases per native label |
| SciFact LoRA | same balanced SciFact subset | 90 | 0.389 | 0.367 | CONTRADICT F1 0.360; 7.5 ms mean latency |
| Ollama zero-shot | same balanced SciFact subset | 90 | 0.533 | 0.433 | CONTRADICT F1 0.000; 3,368.4 ms mean latency |
| SciFact LoRA transfer | five-way ClaimGuard benchmark | 30 | 0.300 | 0.172 | 9.1 ms mean model latency |
| Fast-DetectGPT API | official paired PubMed/GPT-4 passages | 30 | 0.767 | - | P/R/F1 = 1.000/0.533/0.696; AUROC 0.924; 1,018.8 ms |

The embedding run is a real Sentence-Transformer run using the locally cached
`sentence-transformers/all-MiniLM-L6-v2` model. FAISS is unavailable on this Windows setup, so
normalized NumPy cosine similarity was used. On this small benchmark embeddings did not improve
the final label metrics. That negative result is retained rather than hidden.

The real-RQ annotation is a single-annotator dataset (`codex_manual_v1`), so no inter-annotator
agreement can be reported. It contains ten manually selected claim-bearing sentences from each
of the five submitted reports, with document, original sentence index, section, expected type,
citation-needed flag, and annotation rationale.

## Local versus frontier comparison

All backends received the same 30 gold-labeled claim/evidence cases and identical retrieval output.

| Backend | Accuracy | Macro-F1 | Mean latency | Usage |
|---|---:|---:|---:|---|
| Heuristic | 0.867 | 0.868 | 0 ms | no tokens |
| Ollama qwen3:1.7b | 0.733 | 0.728 | 2,744.5 ms | 3,775 prompt + 1,674 generated |
| OpenAI gpt-5.4-mini | 0.633 | 0.518 | 1,424.1 ms | 6,050 input + 1,466 output |
| SciFact LoRA | 0.300 | 0.172 | 6.0 ms | no tokens |

Monetary cost was not logged and is not reconstructed from provider prices.

## SciFact LoRA result

The selected adapter uses `distilbert-base-uncased`, LoRA rank 8 on `q_lin`/`v_lin`, an effective
batch size of 16, seed 42, and three epochs. It trained 740,355 parameters (1.09% of the model) on
all 1,261 SciFact training pairs. Adapter, tokenizer, checkpoints, and provenance are stored in
`outputs/models/scifact-lora`.

On the aligned 90-pair SciFact comparison, LoRA improved over majority by 0.200 Macro-F1 but
trailed local zero-shot prompting by 0.066. LoRA recovered contradiction evidence better, while
Ollama mapped 21/30 contradictions to SUPPORT. The five-label transfer remains lower because
ClaimGuard additionally requires partial support and not-supported.

## Module 4 implementation boundary

- The official Binoculars integration and isolated dependency profile are implemented. The
  calibrated Falcon-7B/Falcon-7B-Instruct pair totals about 14B parameters and cannot fit in the
  available 8 GB VRAM. No Binoculars result is claimed.
- The official Fast-DetectGPT API backend, paragraph scoring, checkpointed CSV evaluator, and
  descriptive citation association are implemented. On 15 original and 15 paired GPT-4 PubMed
  passages it achieved F1 0.696 and AUROC 0.924, with 0/15 human false positives and 7/15 generated
  passages missed. The source data contains no citation markers, so citation association remains
  unmeasured. This score is not proof of authorship.

## Reproducible output files

- `outputs/evaluation/rq_claim_evaluation.json`
- `outputs/evaluation/reference_evaluation.json`
- `outputs/evaluation/evaluation_lexical.json`
- `outputs/evaluation/evaluation_embeddings.json`
- `outputs/evaluation/model_comparison_full.json` and `model_comparison_full.md`
- `outputs/evaluation/module2_validation.json`
- `outputs/evaluation/scifact_lora_vs_zeroshot.json`
- `outputs/evaluation/fast_detect_gpt.json`
- `outputs/evaluation/evaluation_lora.json`
- `outputs/models/scifact-lora/training_report.json` and the saved adapter
- `outputs/examples/rq5_openai.json` and `outputs/examples/rq5_ollama.json`

These numbers are suitable for the report. Official Binoculars execution still requires larger
hardware; a Fast-DetectGPT citation-pattern study requires provenance-labeled, consented text with
real citation markers.
