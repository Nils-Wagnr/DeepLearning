# RQ4 Experiment Details

## What was completed
- Compared all five required approaches: LSTM, LSTM+GloVe, BiLSTM+GloVe+Attention, BERT fine-tuning, and prompting.
- Stored accuracy, macro-F1, training time, inference time per example, parsed-only prompting accuracy, parse rate, and unparsed prompting counts.
- Configured BERT and prompting to use the full IMDB test split by default.
- Added TextCNN comparison from RQ3 and report-ready summary/recommendation sections to the notebook.
- Error analysis exports concrete examples and category counts to `rq4_outputs`.

## Current export status
- LSTM-family and BERT rows are full-test rows (`n_eval_mean=25000`).
- Prompting rows are explicitly marked `STALE_SUBSET_RUN_EXPECTED_25000` because the last executed prompting run used 200 test examples.
- To make the Prompting rows fully assignment-compliant, rerun the Prompting, Plot, Results Table, Error Analysis, and Final Analysis cells after `PROMPT_EVAL_N = None`.

## Key findings from the current full-test trained-model rows
- At n=200, representation effect LSTM -> LSTM+GloVe: +0.0038 accuracy.
- At n=200, architecture/pooling effect LSTM+GloVe -> BiLSTM+GloVe+Attention: +0.1208 accuracy.
- At n=200, contextual pretraining gap BiLSTM+GloVe+Attention -> BERT: -0.0069 accuracy in this run.
- Best trained model at n=200: BiLSTM+GloVe+Attention (0.6288).
- BERT becomes clearly strongest from n=1000 onward.
- BiLSTM+GloVe+Attention at full data: 0.8654 accuracy.
- RQ3 TextCNN best: 0.8710 accuracy, so the fixed BiLSTM is close but does not exceed TextCNN in this run (-0.0056).

## References to cite in the report
- Devlin et al. (2019), BERT.
- Brown et al. (2020), Language Models are Few-Shot Learners.
- Hochreiter and Schmidhuber (1997), LSTM.
- Pennington et al. (2014), GloVe.
- Kim (2014), TextCNN.
