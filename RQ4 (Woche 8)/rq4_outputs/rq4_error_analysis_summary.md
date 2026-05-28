# RQ4 Error Analysis Summary

Exported concrete examples are available in:

- `rq4_error_analysis_examples.csv`
- `rq4_error_analysis_examples.md`

Current exported categories:

| Category | Number of examples |
|---|---:|
| BERT correct, LSTM wrong | 5 |
| Hard examples: all available trained models wrong | 5 |

The current exported examples include review snippets, gold labels, LSTM predictions, BERT predictions, and prompt predictions. Prompt predictions in this export should be treated with the same caveat as the current prompt results table: the notebook code is configured for full-test prompting, but existing prompt outputs must be regenerated for final full-test values.
