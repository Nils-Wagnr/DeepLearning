# Evaluation artifact map

Every report number should be traceable to one of these files. Controlled/synthetic and
authentic-document results are deliberately kept separate.

| Report evidence | Artifact | Reproduction command |
|---|---|---|
| Authentic claim type and citation need (`N=50`) | `../rq_claim_evaluation.json` | `python run_claim_evaluation.py --benchmark data/benchmark/rq_claim_annotations.csv --output outputs/rq_claim_evaluation.json` |
| Five-record parser regression | `../reference_evaluation.json` | `python run_reference_evaluation.py --benchmark data/benchmark/reference_parsing_benchmark.csv --output outputs/reference_evaluation.json` |
| Module-2 gold benchmark (`N=30`) | `module2_validation.json` | `python run_bibliographic_validation_evaluation.py --benchmark data/benchmark/module2_validation_benchmark.csv --output outputs/evaluation/module2_validation.json --timeout 10 --delay 0.75` |
| Lexical five-way verification (`N=30`) | `../evaluation_lexical.json` | `python run_evaluation.py --benchmark data/benchmark/claimguard_benchmark.csv --output outputs/evaluation_lexical.json --verifier heuristic` |
| Embedding five-way verification (`N=30`) | `../evaluation_embeddings.json` | see the embedding-retriever command in the project README |
| Heuristic/Ollama/OpenAI/LoRA comparison | `model_comparison_full.json`, `model_comparison_full.md` | `python run_model_comparison.py --benchmark data/benchmark/claimguard_benchmark.csv --output outputs/evaluation/model_comparison_full.json --markdown-output outputs/evaluation/model_comparison_full.md --verifiers heuristic,ollama,openai,lora` |
| SciFact training and five-label transfer | `../scifact-lora/training_report.json`, `lora_artifact_summary.json`, `model_comparison_full.json` | see the LoRA training command in the project README |
| Crossref metadata-search baseline | `../crossref_baseline_rq5.json` | stored diagnostic over the five RQ5 references |

`openai_no_rag_baseline.json` is intentionally absent until all 30 API calls complete. The
checkpoint-capable command is documented in the README; an incomplete run must not be cited.

Module-2 warnings matter: the saved run records degraded API coverage for 26/30 cases due mainly
to public-service rate limiting. Parser and DOI functionality checks remain directly measurable,
but the final-status metric must be interpreted with that limitation.
