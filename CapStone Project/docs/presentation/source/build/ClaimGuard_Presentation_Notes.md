# ClaimGuard presentation notes

10-minute talk + 5-minute Q&A.

## Slide 1

Nils — 20 seconds
Open with one sentence: ClaimGuard does not decide misconduct; it organizes evidence so a human can review it. Introduce both presenters and the three-part question: claim, reference, support.

## Slide 2

Nils — 55 seconds
Use the contrast on the left. Explain that plagiarism, fabricated references, and unsupported citation use are distinct. ClaimGuard focuses on citation integrity and evidence support. Stress that the system is decision support, not an accusation engine.

## Slide 3

Nils — 45 seconds
Walk left to right. These checks map directly to the three core modules. Mention that every decision remains traceable in JSON, while Markdown is the reviewer-facing view.

## Slide 4

Nils — 55 seconds
Follow the five numbered boxes. Explain that references constrain evidence retrieval; the verifier receives bounded evidence rather than the whole internet. Point out the audit rail: this makes outputs traceable and comparable. Then introduce the module-coverage decision slide.

## Slide 5

Nils — 55 seconds
The three required core modules are complete and visibly evaluated. For optional depth, Module 5 is complete: we trained and saved the LoRA adapter and compared it on aligned and transfer benchmarks. Module 4 is fulfilled through Fast-DetectGPT. We considered Binoculars, but its calibrated Falcon pair totals about 14 billion parameters and does not fit the available 8 GB GPU; using a smaller pair would invalidate its published threshold. Module 6 has a working comparison/import scaffold, but without shared scite or SemanticCite predictions we do not claim a completed external-tool benchmark. This boundary is deliberate: implemented code is separated from measured evidence.

## Slide 6

Nick — 60 seconds
Explain why there is no single best backend. The APIs validate bibliography, not source support. The retriever can use embeddings but falls back to lexical search. Mention store=false for OpenAI and that local models keep text on-device.

## Slide 7

Nick — 75 seconds
If live: run the prepared command, then open rq5_openai.md. If offline: use this slide. Read only the shortened claim. Point to citations and top evidence. Compare the two verdicts, then emphasize that disagreement is exactly why evidence and rationale must be shown.

## Slide 8

Nick — 75 seconds
Start with the 0.900 lexical verifier result, then contrast it with real claim classification at 0.437 Macro-F1. LoRA reached 0.367 on the label-aligned SciFact subset. Fast-DetectGPT reached 0.924 AUROC but only 0.533 recall, missing 7 of 15 generated passages. The takeaway is that every score needs its dataset and failure boundary.

## Slide 9

Nils — 75 seconds
All four backends saw the same retrieved evidence. The heuristic wins this small synthetic benchmark because cases reward direct lexical patterns. LoRA is fastest but cannot emit two of ClaimGuard's five labels. Ollama beat OpenAI here; OpenAI was faster. This is a benchmark-specific finding, not a universal model ranking.

## Slide 10

Nils — 55 seconds
Give two concrete successes and two failures. In manual runs on 7 July 2026, Semantic Scholar requests without an API key and OpenAlex requests with a configured mailto parameter repeatedly returned HTTP 429, even after waiting several minutes and changing the input file. Present this as an observed service condition, not a systematic API-availability benchmark; it can reduce abstract/full-text evidence and lead to insufficient-evidence results. Fast-DetectGPT had no human false positives in this small set, but missed 7 of 15 generated passages. The official benchmark has no citation markers, so no AI-score/citation correlation is claimed. Private reports were not sent to the external detector.

## Slide 11

Nick — 20 seconds; Nils — 15 seconds
Nick summarizes pipeline and evidence. Nils closes with the ethical boundary and invites questions. Transition immediately to the Q&A slide.

## Slide 12

Both — 5 minutes
Suggested ownership: Nils answers architecture/evaluation; Nick answers model/API/demo questions. If asked about the low real-claim score, lead with the measured domain shift and single-annotator limitation.
