# Script index

Run scripts from the repository root as Python modules, for example:

```powershell
python -m scripts.run_claimguard --help
```

- `run_claimguard.py`, `run_ai_detection.py`: document-analysis entry points.
- `run_*_evaluation.py`, `run_evaluation.py`: reproducible module benchmarks.
- `run_model_comparison.py`, `run_scifact_model_comparison.py`: backend comparisons.
- `train_scifact_lora.py`: selected Module-5 training job.
- `prepare_fastdetect_benchmark.py`: deterministic Module-4 benchmark preparation.
- `run_tool_comparison.py`: Module-6 prediction import/comparison scaffold.

Exact report commands and artifact mappings are documented in `outputs/evaluation/README.md`.
