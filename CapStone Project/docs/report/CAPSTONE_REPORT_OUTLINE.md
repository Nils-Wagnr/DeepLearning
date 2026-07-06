# ClaimGuard technical report draft (5-8 pages plus references)

## Abstract

ClaimGuard is a modular pipeline for identifying citation-integrity risks in academic reports.
It extracts and classifies claims, parses and validates references, retrieves source evidence,
and assigns one of five support labels using a transparent heuristic, a local Ollama model, an
OpenAI frontier model, or an optional SciFact LoRA adapter. On a balanced 30-case verification
benchmark, the lexical baseline reached 0.900 Accuracy and 0.900 Macro-F1. A real
Sentence-Transformer retrieval run reached 0.867 Accuracy and 0.868 Macro-F1. On 50 manually
annotated sentences from five course reports, the rule-based claim classifier reached only 0.520
Accuracy and 0.437 Macro-F1; citation-needed detection reached 0.267 F1. The gap between synthetic
and real-report evaluation is the central finding: deterministic rules are useful for triage and
regression tests, but they do not replace expert review. The system therefore exposes evidence,
confidence, backend metadata, and limitations instead of making misconduct decisions.

## 1. Introduction

Academic references can exist bibliographically while still failing to support the statement
that cites them. ClaimGuard separates this problem into three questions: Does a sentence contain
a checkable claim and need a citation? Does the cited work exist and match its bibliographic
record? Does accessible evidence support, partially support, fail to support, or contradict the
claim? The project contributes one reproducible pipeline, comparable verifier interfaces, a
manually annotated real-report set, and human-readable plus machine-readable audit outputs.

## 2. Related work

Discuss SciFact and scientific entailment, MultiVerS, retrieval-augmented generation, bi-encoder
versus cross-encoder retrieval, citation-needed detection, Fast-DetectGPT, and Binoculars. State
explicitly that AI-detection scores have known domain/language/editing failure modes and are not
proof of AI use. Add at least five primary references in the final bibliography.

## 3. Architecture and methods

1. PDF/TXT ingestion cleans extracted text and separates main content, references, and supplied
   evidence.
2. Module 1 performs sentence splitting, section-aware claim typing, citation linking, inherited
   citation handling, and missing-citation severity.
3. Module 2 parses IEEE-like references and validates them through CrossRef, Semantic Scholar,
   OpenAlex, and optionally Unpaywall. The revised parser handles unquoted multi-author IEEE
   records and missing spaces before venues such as `In Proceedings` or `Transactions`.
4. Module 3 chunks evidence and retrieves it lexically or with normalized
   `all-MiniLM-L6-v2` embeddings. All verifier backends receive the same evidence and five-label
   schema.
5. Optional modules provide SciFact LoRA training, Fast-DetectGPT API scoring, and Binoculars
   integration. The scripts record model, seed, device, effective batch size, sample counts,
   evaluation metrics, benchmark hashes, and checkpointed API output.

The manually annotated RQ dataset contains 50 sentences (ten per report). It was labeled once
for claim type and whether a citation is needed. Because there is only one annotator, agreement
statistics are not available. The five-way support benchmark contains 30 balanced, synthetic
claim-evidence cases and is suitable for controlled backend comparisons, not deployment claims.

## 4. Results

| Evaluation | N | Accuracy | Macro-F1 | Additional metric |
|---|---:|---:|---:|---|
| Synthetic claim classification | 25 | 1.000 | 1.000 | citation-needed F1 1.000 |
| Real RQ claim classification | 50 | 0.520 | 0.437 | citation-needed F1 0.267 |
| Reference single-record parsing | 30 | 1.000 | - | one record per input |
| Module-2 final status | 30 | 0.467 | 0.412 | DOI F1 1.000 (N=7); retraction F1 0.667 |
| Five-way verification, lexical | 30 | 0.900 | 0.900 | micro-F1 0.900 |
| Five-way verification, embeddings | 30 | 0.867 | 0.868 | micro-F1 0.867 |
| SciFact LoRA, native validation taxonomy | 450 | 0.409 | 0.353 | 1,261 training pairs |
| SciFact LoRA, ClaimGuard five-way transfer | 30 | 0.300 | 0.172 | mean latency 9.1 ms |
| SciFact LoRA, aligned subset | 90 | 0.389 | 0.367 | majority Macro-F1 0.167 |
| SciFact Ollama zero-shot | 90 | 0.533 | 0.433 | contradiction F1 0.000 |
| Fast-DetectGPT, PubMed/GPT-4 | 30 | 0.767 | - | F1 0.696; AUROC 0.924 |

The real-report result exposes substantial domain shift. Method descriptions were frequently
predicted as factual claims, definitions were often reduced to factual/non-claim labels, and
hedged interpretations were inconsistent. Missing-citation recall was 0.286, so the baseline
must not be presented as a comprehensive detector.

On the balanced support benchmark, contradiction detection was strongest (F1 1.000). The lexical
system confused one supported, one not-supported, and one insufficient-evidence case, while also
overpredicting partial support once. Embedding retrieval did not improve this small benchmark;
its Macro-F1 decreased from 0.900 to 0.868. This can happen because each benchmark item already
contains a short, direct evidence passage for which lexical overlap is highly informative.

On the same 30 gold-labeled cases and identical evidence, heuristic, local `qwen3:1.7b`, OpenAI
`gpt-5.4-mini`, and transferred LoRA reached Macro-F1 0.868, 0.728, 0.518, and 0.172. Mean latency
was approximately 0 ms, 2.74 s, 1.42 s, and 6 ms. This controlled synthetic benchmark is not a
universal model ranking; monetary cost was not logged.

SciFact-LoRA was trained on the RTX 3070 Ti using DistilBERT, rank-8 adapters, and an effective
batch size of 16. It reached 0.353 Macro-F1 on the official 450-pair validation split. On
ClaimGuard's five-way benchmark Macro-F1 fell to 0.172 because the SciFact classifier only models
three labels and cannot emit `partially_supported` or `not_supported`.

## 5. Discussion and limitations

The contrast between perfect synthetic Module-1 results and weak real-RQ results is evidence that
surface-pattern benchmarks overestimate generalization. The support benchmark is also small and
synthetic. API metadata lookup can fail under timeouts or rate limits; PDF extraction introduces
spacing and heading artifacts; abstract-only evidence may be insufficient; model outputs are
non-deterministic; and the manual RQ labels have no second-annotator check.

The official Binoculars threshold is calibrated for Falcon-7B/Falcon-7B-Instruct. Those two
models do not fit in the available 8 GB GPU, and substituting smaller models would require new
threshold calibration. Fast-DetectGPT reached AUROC 0.924 but missed 7/15 generated passages; its
official-data benchmark contains no citation markers, so citation association is unmeasured. The
SciFact result is a single-seed teaching experiment rather than a tuned state-of-the-art result.

## 6. Conclusion

ClaimGuard already provides an auditable end-to-end review workflow and strong controlled
verification performance. Its most important empirical result is not the 0.900 synthetic score,
but the measured failure to transfer simple claim rules to authentic reports. The appropriate use
is therefore evidence-backed triage followed by human review.

## Reproducibility appendix

Record Python/package versions, RTX 3070 Ti hardware, random seed 42, model IDs, API date,
benchmark filenames, and all JSON outputs listed in `docs/FINAL_RESULTS.md`. Never include API
keys, project secrets, or full environment files.
