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

## 2:00-3:30 - Architecture

Walk through PDF ingestion -> sentence/claim analysis -> reference APIs -> evidence retrieval ->
verifier -> JSON and Markdown. Emphasize that every model backend uses the same output schema and
records model, latency, evidence, confidence, and token metadata.

## 3:30-5:00 - Technical depth

Explain lexical retrieval versus normalized `all-MiniLM-L6-v2` cosine retrieval. Show the fixed
IEEE parser example from Report 5. Briefly explain LoRA adapters and why the SciFact training
script uses gradient accumulation and portable `all-linear` targets.

## 5:00-6:30 - Live demo

Run the bad sample and open the concise Markdown report. Keep `outputs/rq5_openai.md`,
`outputs/rq5_ollama.md`, and `outputs/model_comparison.md` ready as offline fallbacks.

## 6:30-8:15 - Evaluation

Use this table on the results slide:

| Test | N | Accuracy | Macro-F1 |
|---|---:|---:|---:|
| Real RQ claims | 50 | 0.520 | 0.437 |
| IEEE parser | 5 | 1.000 | - |
| Lexical verification | 30 | 0.900 | 0.900 |
| Embedding verification | 30 | 0.867 | 0.868 |
| SciFact LoRA validation | 450 | 0.409 | 0.353 |
| LoRA five-way transfer | 30 | 0.300 | 0.172 |

Add below the table: real-RQ citation-needed P/R/F1 = 0.250/0.286/0.267. The key story is the
large synthetic-to-real gap, not a perfect demo score.

Explain the LoRA taxonomy mismatch in one sentence: SciFact has three output labels, while
ClaimGuard evaluates five; the trained head therefore cannot predict two benchmark classes.

## 8:15-9:15 - Local versus frontier and failure case

For one actual RQ5 request, OpenAI used 506 tokens and 1.889 s; Ollama took 40.902 s and generated
447 tokens. They also disagreed on the label. Explain that this is diagnostic evidence, not a
gold-label benchmark. Then show one methodological sentence that the regex baseline mislabeled as
a factual claim.

## 9:15-10:00 - Ethics and conclusion

ClaimGuard prioritizes suspicious passages; it does not prove deception or authorship. Binoculars
is optional and requires human supervision. End with: controlled verification is promising, but
real-report claim detection needs learned models, more annotation, and a second annotator.
