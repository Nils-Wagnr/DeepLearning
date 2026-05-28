| N | LSTM acc. | Representation gap | Architecture/pooling gap | Contextual gap | Total BERT-LSTM gap |
|---:|---:|---:|---:|---:|---:|
| 50 | 0.5061 | -0.0037 | 0.0435 | 0.0097 | 0.0495 |
| 200 | 0.5043 | 0.0038 | 0.1208 | -0.0069 | 0.1176 |
| 1000 | 0.5086 | 0.0125 | 0.2293 | 0.1157 | 0.3575 |
| 5000 | 0.5797 | -0.0054 | 0.2603 | 0.0582 | 0.3131 |
| 25000 | 0.7831 | 0.0503 | 0.0321 | 0.0491 | 0.1314 |

Gap definitions:

- Representation gap: LSTM + GloVe minus LSTM with random embeddings.
- Architecture/pooling gap: BiLSTM + GloVe + attention minus LSTM + GloVe.
- Contextual gap: BERT minus BiLSTM + GloVe + attention.
- Total gap: BERT minus LSTM with random embeddings.
