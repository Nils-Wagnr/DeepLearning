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

Nils — 70 seconds
Follow the five numbered boxes. Explain that references constrain evidence retrieval; the verifier never receives the whole internet. Point out the audit rail: this is what makes the output reproducible. Hand over to Nick for implementation choices.

## Slide 5

Nick — 75 seconds
Explain why there is no single best backend. The APIs validate bibliography, not source support. The retriever can use embeddings but falls back to lexical search. Mention store=false for OpenAI and that local models keep text on-device.

## Slide 6

Nick — 90 seconds
If live: run the prepared command, then open rq5_openai.md. If offline: use this slide. Read only the shortened claim. Point to citations and top evidence. Compare the two verdicts, then emphasize that disagreement is exactly why evidence and rationale must be shown.

## Slide 7

Nick — 75 seconds
Start with the 0.900 lexical verifier result, then contrast it with real claim classification at 0.437 Macro-F1. Explain that embeddings did not help this small direct-evidence benchmark. Mention the parser result cautiously: only five cases. The takeaway is the synthetic-to-real gap.

## Slide 8

Nils — 75 seconds
Separate gold-benchmark results from the dagger-marked one-claim diagnostic. The heuristic wins this small synthetic benchmark because the cases reward direct lexical patterns. LoRA is fast but cannot emit two of ClaimGuard's five labels. OpenAI is much faster than the small Ollama run here, but a full gold comparison is still pending.

## Slide 9

Nils — 55 seconds
Give two concrete successes and two concrete failures. Do not apologize for limitations; frame them as measured engineering evidence. Mention Binoculars only as implemented but not executable with the calibrated models on 8 GB VRAM.

## Slide 10

Nick — 20 seconds; Nils — 15 seconds
Nick summarizes pipeline and evidence. Nils closes with the ethical boundary and invites questions. Transition immediately to the Q&A slide.

## Slide 11

Both — 5 minutes
Suggested ownership: Nils answers architecture/evaluation; Nick answers model/API/demo questions. If asked about the low real-claim score, lead with the measured domain shift and single-annotator limitation.
