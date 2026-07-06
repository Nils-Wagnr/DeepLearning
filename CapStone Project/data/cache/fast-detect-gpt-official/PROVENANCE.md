# Fast-DetectGPT benchmark source

- Upstream: `https://github.com/baoguangsheng/fast-detect-gpt`
- Pinned commit: `971b05202bac2bb504d60c0ac0812fea7a8f7c82`
- Benchmark input: `exp_gpt3to4/data/pubmed_gpt-4.raw_data.json`
- License: MIT (`LICENSE` in this directory)
- Local selection: 15 paired original/GPT-4 examples, seed 42, minimum 40 words per member

The generated 30-row selection is stored at
`data/benchmark/ai_detection_benchmark.csv`. The original passages are treated as human and the
paired sampled passages as AI-generated, following the upstream file's provenance. The dataset
contains no citation annotations.
