# RQ4 Experiment Details
## What was completed
- Added structured per-seed metrics for accuracy, macro-F1, training time, and inference time per example.
- BERT evaluation now uses the full IMDB test split by default; reduced evaluation is only used if BERT_EVAL_MAX_EXAMPLES is set.
- Prompting evaluation now uses random balanced test subsets and stores unparsed counts, parse rate, parsed-only accuracy, and all-case accuracy.
- Error analysis exports concrete examples for direct report use.

## Experiment setup
- Training sizes configured in the notebook: [50, 200, 1000, 5000, 25000].
- Number of seeds configured in the notebook: 3.
- Training subsets are balanced by the provided get_subset helper.
- LSTM-family models evaluate on the full IMDB test split.
- BERT evaluation: full IMDB test split.
- Prompting evaluation: random balanced test subsets with n=200 per seed.

## Result table
| Model | N | Accuracy mean | Accuracy std | Macro-F1 mean | Macro-F1 std | Train time mean | Inference time/example | Parse rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LSTM | 50 | 0.5061 | 0.0031 | 0.4557 | 0.0353 | 0.03 | 0.000028 |  |
| LSTM | 200 | 0.5043 | 0.0016 | 0.4561 | 0.0213 | 0.14 | 0.000029 |  |
| LSTM | 1000 | 0.5086 | 0.0041 | 0.4699 | 0.0111 | 0.57 | 0.000028 |  |
| LSTM | 5000 | 0.5797 | 0.0456 | 0.5660 | 0.0619 | 2.85 | 0.000028 |  |
| LSTM | 25000 | 0.7831 | 0.0226 | 0.7829 | 0.0225 | 14.10 | 0.000028 |  |
| LSTM+GloVe | 50 | 0.5023 | 0.0055 | 0.5001 | 0.0057 | 0.03 | 0.000028 |  |
| LSTM+GloVe | 200 | 0.5081 | 0.0072 | 0.4708 | 0.0490 | 0.11 | 0.000028 |  |
| LSTM+GloVe | 1000 | 0.5210 | 0.0120 | 0.4730 | 0.0425 | 0.48 | 0.000028 |  |
| LSTM+GloVe | 5000 | 0.5744 | 0.0247 | 0.5277 | 0.0370 | 2.38 | 0.000028 |  |
| LSTM+GloVe | 25000 | 0.8333 | 0.0170 | 0.8324 | 0.0182 | 11.95 | 0.000029 |  |
| BiLSTM+Attn | 50 | 0.5459 | 0.0159 | 0.5067 | 0.0415 | 0.05 | 0.000045 |  |
| BiLSTM+Attn | 200 | 0.6288 | 0.0213 | 0.6189 | 0.0271 | 0.22 | 0.000045 |  |
| BiLSTM+Attn | 1000 | 0.7504 | 0.0066 | 0.7478 | 0.0084 | 1.02 | 0.000045 |  |
| BiLSTM+Attn | 5000 | 0.8347 | 0.0023 | 0.8342 | 0.0024 | 5.05 | 0.000045 |  |
| BiLSTM+Attn | 25000 | 0.8654 | 0.0016 | 0.8653 | 0.0016 | 25.12 | 0.000045 |  |
| BERT | 50 | 0.5556 | 0.0407 | 0.4866 | 0.1087 | 0.96 | 0.000871 |  |
| BERT | 200 | 0.6219 | 0.0532 | 0.5669 | 0.0953 | 2.69 | 0.000870 |  |
| BERT | 1000 | 0.8661 | 0.0021 | 0.8660 | 0.0021 | 12.10 | 0.000872 |  |
| BERT | 5000 | 0.8929 | 0.0021 | 0.8929 | 0.0021 | 64.66 | 0.000954 |  |
| BERT | 25000 | 0.9145 | 0.0001 | 0.9145 | 0.0001 | 318.92 | 0.000932 |  |
| Prompt-ZS | 0 | 0.0383 | 0.0024 | 0.0664 | 0.0045 | 0.00 | 0.033147 | 0.0967 |
| Prompt-2shot | 2 | 0.4750 | 0.0308 | 0.4370 | 0.0389 | 0.00 | 0.032892 | 0.9750 |
| Prompt-4shot | 4 | 0.5017 | 0.0448 | 0.4813 | 0.0610 | 0.00 | 0.032664 | 0.9933 |
| Prompt-8shot | 8 | 0.5683 | 0.0125 | 0.5539 | 0.0153 | 0.00 | 0.039386 | 1.0000 |

## Gap decomposition
- Reference size: n=200.
- Representation effect, LSTM -> LSTM+GloVe: +0.0038.
- Architecture/pooling effect, LSTM+GloVe -> BiLSTM+Attn: +0.1208.
- Contextual pretraining gap, BiLSTM+Attn -> BERT: -0.0069.

## Practical notes
- With 0 labels, use prompting, preferably with a stronger instruction-tuned model than GPT-2.
- With 50-200 labels, compare DistilBERT and BiLSTM+GloVe+Attn; the best choice depends on the observed accuracy/time trade-off.
- With 1000+ labels, fine-tuning DistilBERT/BERT is usually the strongest candidate if compute is available.
- If inference cost matters, LSTM-family models are usually cheaper than prompting.

## Limitations
- GPT-2 is not instruction-tuned, so prompting results should be interpreted as a weak local baseline.
- If BERT_EVAL_MAX_EXAMPLES is set for runtime, report the configured random balanced subset size instead of claiming full-test evaluation.
