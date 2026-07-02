# ClaimGuard model comparison

Benchmark: `data\benchmark\claimguard_benchmark.csv`

## Leaderboard

| Backend | Accuracy | Macro-F1 | Mean latency | Model calls |
|---|---:|---:|---:|---:|
| heuristic | 0.900 | 0.900 | 0.0 ms | 0 |
| lora | 0.300 | 0.172 | 9.3 ms | 25 |

## Backend details

### heuristic

Accuracy **0.900**, Macro-F1 **0.900**.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| supported | 0.833 | 0.833 | 0.833 | 6 |
| partially_supported | 0.857 | 1.000 | 0.923 | 6 |
| not_supported | 0.833 | 0.833 | 0.833 | 6 |
| contradicted | 1.000 | 1.000 | 1.000 | 6 |
| insufficient_evidence | 1.000 | 0.833 | 0.909 | 6 |

Representative errors:

- `S6`: expected **supported**, predicted **partially_supported** (confidence 0.438).
- `N5`: expected **not_supported**, predicted **supported** (confidence 0.562).
- `I6`: expected **insufficient_evidence**, predicted **not_supported** (confidence 0.187).

### lora

Accuracy **0.300**, Macro-F1 **0.172**.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| supported | 0.375 | 0.500 | 0.429 | 6 |
| partially_supported | 0.000 | 0.000 | 0.000 | 6 |
| not_supported | 0.000 | 0.000 | 0.000 | 6 |
| contradicted | 0.000 | 0.000 | 0.000 | 6 |
| insufficient_evidence | 0.273 | 1.000 | 0.429 | 6 |

Representative errors:

- `S2`: expected **supported**, predicted **insufficient_evidence** (confidence 0.595).
- `P1`: expected **partially_supported**, predicted **insufficient_evidence** (confidence 0.508).
- `P2`: expected **partially_supported**, predicted **insufficient_evidence** (confidence 0.396).

## Interpretation limits

- Compare backends only when they were run on the same benchmark and retrieval setup.
- API and local-model latency depend on hardware, network load, and warm-up state.
- This report records evidence, not proof of academic misconduct.
