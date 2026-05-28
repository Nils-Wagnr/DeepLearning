# RQ4 Experiment Details

This file is intentionally separate from the notebook so the notebook can stay minimal and clear.
After the notebook experiments run, the final analysis cell updates this file with the computed
result table and gap decomposition.

## What Was Changed

- Only the analysis/reporting sections marked in the notebook were completed.
- The existing model definitions and experiment loops were preserved.
- The central accuracy-vs-size figure now prints crossover notes and saves `rq4_accuracy_vs_size.png`.
- The results table cell now saves `rq4_outputs/rq4_results_table.csv` and `rq4_outputs/rq4_results_table.md`.
- The error-analysis cell trains one small n=200 LSTM and one small n=200 BERT model, then prints examples.
- The final analysis cell writes this file again with computed results after the notebook has run.

## Experiment Design

- Dataset: IMDB sentiment classification.
- Training sizes from the template: `50`, `200`, `1000`, `5000`, and `25000`.
- Repeats: controlled by `N_SEEDS` in the notebook.
- Models compared:
  - LSTM with random embeddings.
  - LSTM with frozen GloVe embeddings.
  - BiLSTM with frozen GloVe embeddings and attention pooling.
  - Fine-tuned DistilBERT/BERT, depending on `BERT_MODEL`.
  - Prompting baselines: zero-shot and few-shot with k = 2, 4, 8.

## Notes and Limitations

- The original template stores accuracy mean/std in `results`; it prints training time but does not store it structurally.
- Prompting is evaluated on a reduced subset by the template because generation is slow.
- GPT-2 is a weak local prompting baseline because it is not instruction-tuned.
- BERT evaluation in the original template uses a reduced test subset for speed.
- For final report-quality results, rerun with the desired sizes and seeds before using the generated tables.
