# RQ4 Experiment Details
## What was completed
- Filled only the requested notebook analysis sections: central-figure interpretation, results export, error analysis, and short analysis.
- The original model and experiment structure was kept intact.
- Results are computed from the notebook `results` dictionary; no values are hardcoded.

## Experiment setup
- Training sizes configured in the notebook: [50, 200, 1000, 5000, 25000].
- Number of seeds configured in the notebook: 3.
- Training subsets are balanced by the provided `get_subset` helper.
- LSTM and GloVe models evaluate on `test_ds`; BERT uses its own configured evaluation sample in `train_bert`.
- Prompting uses a reduced test subset in the template (`max_test=200`) because generation is slow.

## Result table
| Approach | N | Accuracy mean | Accuracy std |
|---|---:|---:|---:|
| LSTM | 50 | 0.5066 | 0.0021 |
| LSTM | 200 | 0.5033 | 0.0041 |
| LSTM | 1000 | 0.5069 | 0.0061 |
| LSTM | 5000 | 0.5932 | 0.0520 |
| LSTM | 25000 | 0.7831 | 0.0226 |
| LSTM+GloVe | 50 | 0.5022 | 0.0059 |
| LSTM+GloVe | 200 | 0.5098 | 0.0063 |
| LSTM+GloVe | 1000 | 0.5197 | 0.0063 |
| LSTM+GloVe | 5000 | 0.5427 | 0.0350 |
| LSTM+GloVe | 25000 | 0.8333 | 0.0170 |
| BiLSTM+Attn | 50 | 0.5529 | 0.0216 |
| BiLSTM+Attn | 200 | 0.6002 | 0.0415 |
| BiLSTM+Attn | 1000 | 0.7418 | 0.0035 |
| BiLSTM+Attn | 5000 | 0.8369 | 0.0023 |
| BiLSTM+Attn | 25000 | 0.8654 | 0.0016 |
| BERT | 50 | 0.8778 | 0.1622 |
| BERT | 200 | 0.7275 | 0.0748 |
| BERT | 1000 | 0.8620 | 0.0193 |
| BERT | 5000 | 0.8932 | 0.0036 |
| BERT | 25000 | 0.9175 | 0.0000 |
| Prompt-ZS | 0 | 0.1538 | 0.0000 |
| Prompt-2shot | 2 | 0.1766 | 0.0131 |
| Prompt-4shot | 4 | 0.2583 | 0.0891 |
| Prompt-8shot | 8 | 0.3872 | 0.0904 |

## Gap decomposition
- Reference size: n=200.
- Representation effect, LSTM -> LSTM+GloVe: +0.0065.
- Architecture/pooling effect, LSTM+GloVe -> BiLSTM+Attn: +0.0904.
- Contextual pretraining gap, BiLSTM+Attn -> BERT: +0.1273.

## Practical notes
- With 0 labels, use prompting, preferably with a stronger instruction-tuned model than GPT-2.
- With 50-200 labels, compare DistilBERT and BiLSTM+GloVe+Attn; the best choice depends on the observed accuracy/time trade-off.
- With 1000+ labels, fine-tuning DistilBERT/BERT is usually the strongest candidate if compute is available.
- If inference cost matters, LSTM-family models are usually cheaper than prompting.

## Limitations
- The template stores accuracy mean/std, but not structured training time or macro F1. Training times are printed during runs.
- BERT in the template evaluates on a 2,000-example test sample for speed unless changed.
- Prompting uses a reduced evaluation subset for runtime.
- GPT-2 is not instruction-tuned, so prompting results should be interpreted as a weak local baseline.
