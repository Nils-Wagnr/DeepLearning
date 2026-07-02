# ClaimGuard integrity report

Input: `Reports\NW2_RQ5_Report.pdf`

Verifier: `ollama`

## Summary

- Sentences: 137
- Factual claims: 65
- Citation-needed flags: 21
- Parsed references: 5
- Reference validation: {'api_unavailable': 4, 'unverified': 1}
- Claim verification: {'supported': 1, 'insufficient_evidence': 1}

## Citation-needed flags

### Sentence 0 — medium

Deep Learning (285652) Cutting Context Right: Chunking Strategies and Cross-Encoder Reranking for RAG Wagner Nils∗ Wenzel Nick† June 10, 2026 Submitted to Carsten Lanquillon ∗212405,nwagner1@stud.hs-heilbronn.de †207678,nwenzel@stud.hs-heilbronn.de Deep Learning: RQ5 Chunking & Reranking1 1 Abstract.

### Sentence 4 — high

Dense retrieval uses all-MiniLM-L6-v2 embeddings with a normalized IndexFlatIPFAISS index.

### Sentence 6 — medium

The strongest bi-encoder-only configuration is sentence-based splitting with size128and overlap 0or50, reaching Recall@5= 1 .000and MRR= 0 .946.

### Sentence 7 — medium

The best reranked configuration is sentence-based splitting with size512and no overlap, reaching Recall@5= 1.000and MRR@5 = 0.971.

### Sentence 8 — medium

Answer accuracy was evaluated withgoogle/flan-t5-small for three representative configurations and reached0.40,0 .05, and0 .00, showing that strong retrieval alone does not guarantee strong generation.

### Sentence 12 — high

In such a system, the retrieval stage is a central bottleneck: if the relevant evidence is not retrieved, the generator cannot reliably produce a grounded answer.

### Sentence 104 — medium

Deep Learning: RQ5 Chunking & Reranking6 5 Discussion.

### Sentence 106 — medium

It reaches Recall@5= 1.000and the highest observed MRR@5 of 0.971.

### Sentence 110 — medium

It reaches Recall@5= 1 .000and MRR= 0 .946without the reranking stage.

### Sentence 112 — medium

However, the answer accuracy experiment shows that small chunks do not automatically guarantee strong final answers, because generation quality depends on how well the retrieved context can be synthesized by the model.

### Sentence 118 — medium

It improves some fixed-size settings, which is plausible because fixed windows can cut through relevant information.

### Sentence 121 — high

Sentence-based and recursive splitting both outperform fixed-size splitting in the strongest configurations.

### Sentence 123 — medium

The best single configuration is sentence-based, and the best fixed-size setting requires overlap to match the perfect Recall@5 of the better boundary-aware methods.

### Sentence 124 — medium

The best configuration has no top-5 retrieval failures.

### Sentence 126 — high

Five diagnostic failures are reported.

### Sentence 127 — medium

Three are reranking regressions: for the ImageNet benchmark question, the gold documentComputer visionwas present before reranking but displaced from the final top-5 in recursive size128 settings and fixed size256.

### Sentence 129 — medium

One failure is classified as a boundary or representation miss, where the relevant document was absent from the top-20 candidate pool.

### Sentence 131 — medium

The main limitations are the small corpus size, the use of only one embedding model, the use of only one cross-encoder reranker, and the article-level relevance definition.

### Sentence 132 — high

Since a chunk Deep Learning: RQ5 Chunking & Reranking7 is relevant if it comes from the correct source article, the evaluation does not verify that the retrieved chunk contains the exact evidence sentence.

### Sentence 135 — medium

For a similar Wikipedia-style RAG corpus, the practical recommendation is to use sentencebased chunking with a medium chunk size around512characters, no overlap, top-20 bi-encoder retrieval, and cross-encoder reranking to the final top-5 when retrieval precision is more important than latency.

### Sentence 136 — medium

If latency is the dominant constraint, sentence-based splitting with size128and no reranking is a strong fallback because it already reaches Recall@5= 1.000and MRR= 0 .946 in this experiment.

## Source-support review

### Sentence 11 — supported

Retrieval-Augmented Generation (RAG) connects a language model to external knowledge without changing the model weights [1, 3].

- Backend: `ollama`
- Model: `qwen3:1.7b`
- Confidence: `1.0`
- Latency: `40902 ms`
- Cited references: `1, 3`
- Tokens: input `n/a`, output `n/a`, total `n/a`
- Response ID: `n/a`

Rationale: The evidence directly establishes that Retrieval-Augmented Generation (RAG) involves connecting a language model to external knowledge, as described in the cited papers. Both sources mention the integration of external knowledge through retrieval methods, without modifying the model weights. The claims are consistent across the provided sources, and the evidence is sufficient to confirm the statement.

Top evidence (`reference:3`, score `0.335`):

> Gao, Y. Authors: Gao, Xiong, Jia, Pan, Bi, Dai, Sun. Year: 2024. [3] Y. Gao, Y. Xiong, X. Gao, K. Jia, J. Pan, Y. Bi, Y. Dai, J. Sun, M. Wang, and H. Wang. Retrieval-Augmented Generation for Large Language Models: A Survey.arXiv preprint arXiv:2312.10997, 2024.

### Sentence 23 — insufficient_evidence

However, it cannot model detailed token-level interactions between the query and a candidate chunk [2].

- Backend: `ollama`
- Model: `not called`
- Confidence: `0.0`
- Latency: `n/a ms`
- Cited references: `2`
- Tokens: input `n/a`, output `n/a`, total `n/a`
- Response ID: `n/a`

Rationale: No relevant evidence chunks were retrieved for the cited source.

## Interpretation warning

ClaimGuard is a triage tool. Every flag requires human review; AI-text scores are not proof of authorship.
