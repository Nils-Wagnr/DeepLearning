# ClaimGuard: 10-minute presentation with measured results

## 0:00-1:00 - Motivation

Show one claim whose citation exists but whose accessible evidence does not establish the claim.
Key sentence: ClaimGuard checks citation presence, bibliographic existence, and source support as
three separate problems.

## 1:00-2:00 - Research questions

- Can the pipeline find claims that need citations?
- Can it parse and validate IEEE-style references from real PDFs?
- Can retrieved evidence distinguish five support states?
- What changes between lexical, embedding, local-model, and frontier-model paths?

## 2:00-2:55 - Architecture

Walk through PDF ingestion -> sentence/claim analysis -> reference APIs -> evidence retrieval ->
verifier -> JSON and Markdown. Emphasize that every model backend uses the same output schema and
records model, latency, evidence, confidence, and token metadata.

## 2:55-3:50 - Module coverage

State the evidence boundary explicitly: Core Modules 1--3 are complete and evaluated. Optional
Module 5 is complete through the trained SciFact LoRA adapter and aligned comparison. Optional
Module 4 is complete through the evaluated Fast-DetectGPT integration; Binoculars was considered
but its calibrated 14B model pair does not fit the available 8 GB GPU, and replacing the pair
would invalidate its published threshold. Module 6 has a reusable comparison/import scaffold but
no completed scite or SemanticCite predictions, so it remains future work.

## 3:50-4:50 - Technical depth

Explain lexical retrieval versus normalized `all-MiniLM-L6-v2` cosine retrieval. Show the fixed
IEEE parser example from Report 5. Briefly explain LoRA adapters and why the SciFact training
script uses gradient accumulation and portable `all-linear` targets.

## 4:50-6:05 - Recorded UI demo

Use the embedded 20-second recording from the real RQ5 PDF. It shows upload, the reviewer
overview, and the automatic heuristic-versus-Ollama comparison. Emphasize that disagreements
identify passages for human inspection; they do not establish which model is correct. Keep
`ClaimGuard_UI_Demo.mp4` beside the deck as a playback fallback. The original static demo slide
and `outputs/examples/rq5_openai.md` remain available if embedded media is blocked.

## 6:05-7:20 - Evaluation

Use this table on the results slide:

| Test | N | Accuracy | Macro-F1 |
|---|---:|---:|---:|
| Real RQ claims | 50 | 0.520 | 0.437 |
| Reference parsing | 30 | 1.000 | - |
| Lexical verification | 30 | 0.900 | 0.900 |
| Embedding verification | 30 | 0.867 | 0.868 |
| SciFact LoRA validation | 450 | 0.409 | 0.353 |
| LoRA five-way transfer | 30 | 0.300 | 0.172 |
| Fast-DetectGPT (15 human + 15 GPT-4) | 30 | 0.767 | F1 0.696; AUROC 0.924 |

Add below the table: real-RQ citation-needed P/R/F1 = 0.250/0.286/0.267. The key story is the
large synthetic-to-real gap, not a perfect demo score.

Explain the LoRA taxonomy mismatch in one sentence: SciFact has three output labels, while
ClaimGuard evaluates five; the trained head therefore cannot predict two benchmark classes.

## 7:20-8:35 - Local versus frontier and failure case

On the same 30 gold-labeled claim/evidence cases, heuristic, Ollama, OpenAI, and LoRA reached
Macro-F1 0.868, 0.728, 0.518, and 0.172. Mean latencies were approximately 0 ms, 2.74 s, 1.42 s,
and 6 ms. Explain that this controlled benchmark favors direct lexical patterns and is not a
universal model ranking.

## 8:35-10:00 - Ethics and conclusion

ClaimGuard prioritizes suspicious passages; it does not prove deception or authorship. Fast-DetectGPT
missed 7/15 GPT-4 passages despite AUROC 0.924, and the benchmark has no citations for correlation.
End with: controlled verification is promising, but real-report detection needs more annotation,
external baselines, and a consented citation-pattern study.
