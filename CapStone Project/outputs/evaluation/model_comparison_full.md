# ClaimGuard model comparison

Benchmark: `data\benchmark\claimguard_benchmark.csv`

## Leaderboard

| Backend | N | Accuracy | Macro-F1 | Mean latency | Model calls | Tokens | Cost | Typical failure |
|---|---:|---:|---:|---:|---:|---|---|---|
| heuristic | 30 | 0.867 | 0.868 | 0.0 ms | 0 | not logged | not_logged | partially_supported -> supported (2 cases) |
| ollama | 30 | 0.733 | 0.728 | 2744.5 ms | 27 | 3775 prompt / 1674 generated | not_logged | partially_supported -> supported (3 cases) |
| openai | 30 | 0.633 | 0.518 | 1424.1 ms | 27 | 6050 in / 1466 out (7516 total) | not_logged | not_supported -> insufficient_evidence (5 cases) |
| lora | 30 | 0.300 | 0.172 | 6.0 ms | 27 | not logged | not_logged | partially_supported -> insufficient_evidence (6 cases) |

## Pairwise agreement

| Backends | Shared N | Agreement |
|---|---:|---:|
| heuristic vs openai | 30 | 0.633 |
| heuristic vs ollama | 30 | 0.733 |
| heuristic vs lora | 30 | 0.267 |
| openai vs ollama | 30 | 0.567 |
| openai vs lora | 30 | 0.433 |
| ollama vs lora | 30 | 0.200 |

## Backend details

### heuristic

Accuracy **0.867**, Macro-F1 **0.868**.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| supported | 0.667 | 1.000 | 0.800 | 6 |
| partially_supported | 1.000 | 0.667 | 0.800 | 6 |
| not_supported | 0.833 | 0.833 | 0.833 | 6 |
| contradicted | 1.000 | 1.000 | 1.000 | 6 |
| insufficient_evidence | 1.000 | 0.833 | 0.909 | 6 |

Representative errors:

- `P3`: expected **partially_supported**, predicted **supported** (confidence 0.573).
- `P4`: expected **partially_supported**, predicted **supported** (confidence 0.587).
- `N5`: expected **not_supported**, predicted **supported** (confidence 0.684).

### openai

Accuracy **0.633**, Macro-F1 **0.518**.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| supported | 0.667 | 1.000 | 0.800 | 6 |
| partially_supported | 1.000 | 0.167 | 0.286 | 6 |
| not_supported | 0.000 | 0.000 | 0.000 | 6 |
| contradicted | 0.667 | 1.000 | 0.800 | 6 |
| insufficient_evidence | 0.545 | 1.000 | 0.706 | 6 |

Representative errors:

- `P1`: expected **partially_supported**, predicted **supported** (confidence 0.980).
- `P2`: expected **partially_supported**, predicted **supported** (confidence 0.930).
- `P3`: expected **partially_supported**, predicted **supported** (confidence 0.960).

### ollama

Accuracy **0.733**, Macro-F1 **0.728**.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| supported | 0.667 | 1.000 | 0.800 | 6 |
| partially_supported | 1.000 | 0.500 | 0.667 | 6 |
| not_supported | 0.545 | 1.000 | 0.706 | 6 |
| contradicted | 1.000 | 0.667 | 0.800 | 6 |
| insufficient_evidence | 1.000 | 0.500 | 0.667 | 6 |

Representative errors:

- `P1`: expected **partially_supported**, predicted **supported** (confidence 1.000).
- `P2`: expected **partially_supported**, predicted **supported** (confidence 1.000).
- `P3`: expected **partially_supported**, predicted **supported** (confidence 0.950).

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
