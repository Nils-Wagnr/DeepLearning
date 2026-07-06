# Evaluation artifact map

Every report number should be traceable to one of these files. Controlled/synthetic and
authentic-document results are deliberately kept separate.

The saved 2 July model-comparison JSON files retain the adapter path used during execution
(`outputs/scifact-lora`). The unchanged adapter now lives at `outputs/models/scifact-lora`; this
organizational move does not alter any recorded prediction or metric.

| Report evidence | Artifact | Reproduction command |
|---|---|---|
| Authentic claim type and citation need (`N=50`) | `rq_claim_evaluation.json` | `python -m scripts.run_claim_evaluation --benchmark data/benchmark/rq_claim_annotations.csv --output outputs/evaluation/rq_claim_evaluation.json` |
| Five-record parser regression | `reference_evaluation.json` | `python -m scripts.run_reference_evaluation --benchmark data/benchmark/reference_parsing_benchmark.csv --output outputs/evaluation/reference_evaluation.json` |
| Module-2 gold benchmark (`N=30`) | `module2_validation.json` | `python -m scripts.run_bibliographic_validation_evaluation --benchmark data/benchmark/module2_validation_benchmark.csv --output outputs/evaluation/module2_validation.json --timeout 10 --delay 0.75` |
| Lexical five-way verification (`N=30`) | `evaluation_lexical.json` | `python -m scripts.run_evaluation --benchmark data/benchmark/claimguard_benchmark.csv --output outputs/evaluation/evaluation_lexical.json --verifier heuristic` |
| Embedding five-way verification (`N=30`) | `evaluation_embeddings.json` | see the embedding-retriever command in the project README |
| Heuristic/Ollama/OpenAI/LoRA comparison | `model_comparison_full.json`, `model_comparison_full.md` | `python -m scripts.run_model_comparison --benchmark data/benchmark/claimguard_benchmark.csv --output outputs/evaluation/model_comparison_full.json --markdown-output outputs/evaluation/model_comparison_full.md --verifiers heuristic,ollama,openai,lora` |
| SciFact training and five-label transfer | `../models/scifact-lora/training_report.json`, `lora_artifact_summary.json`, `model_comparison_full.json` | see the LoRA training command in the project README |
| Aligned SciFact LoRA vs zero-shot comparison (`N=90`) | `scifact_lora_vs_zeroshot.json` | `python -m scripts.run_scifact_model_comparison --archive data/cache/scifact-data.tar.gz --adapter outputs/models/scifact-lora --per-label 30 --seed 42 --output outputs/evaluation/scifact_lora_vs_zeroshot.json` |
| Fast-DetectGPT original/GPT-4 benchmark (`N=30`) | `fast_detect_gpt.json` | `python -m scripts.run_ai_detection_evaluation --benchmark data/benchmark/ai_detection_benchmark.csv --output outputs/evaluation/fast_detect_gpt.json --method fast_detect_gpt --retries 3` |
| Crossref metadata-search baseline | `crossref_baseline_rq5.json` | stored diagnostic over the five RQ5 references |

`openai_no_rag_baseline.json` is intentionally absent until all 30 API calls complete. The
checkpoint-capable command is documented in the README; an incomplete run must not be cited.

Module-2 warnings matter: the saved run records degraded API coverage for 26/30 cases due mainly
to public-service rate limiting. Parser and DOI functionality checks remain directly measurable,
but the final-status metric must be interpreted with that limitation.

Module 4 has a completed official-data artifact: 15 original and 15 paired GPT-4 PubMed passages,
Accuracy 0.767, F1 0.696, AUROC 0.924, and 1,018.8 ms mean latency. The benchmark was generated
with seed 42 from official repository commit `971b052`. It contains no citation markers, so it
cannot support a detector--citation correlation claim.
