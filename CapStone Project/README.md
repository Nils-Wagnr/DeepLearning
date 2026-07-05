# ClaimGuard

ClaimGuard is an end-to-end academic writing integrity checker built for the MWI Deep
Learning Capstone Project. It accepts PDF or plain-text documents and produces both a
machine-readable JSON report and an optional concise Markdown review.

The application contains all three core modules and executable paths for the three optional
modules from the assignment:

1. Claim extraction, citation linking, citation-needed severity, and section awareness.
2. Bibliographic extraction and validation through CrossRef, Semantic Scholar, and OpenAlex.
3. RAG evidence retrieval plus heuristic, Ollama, OpenAI, or SciFact-LoRA verification.
4. Optional AI-generated-text detection through the Binoculars reference implementation.
5. Optional LoRA fine-tuning on SciFact.
6. Shared benchmark comparison for ClaimGuard, model backends, and external tools.

All optional network and model features are opt-in. The base application remains deterministic
and runnable offline.

## Interactive frontend

ClaimGuard includes a German Streamlit interface for uploads, pasted text, sample documents,
claim-by-claim evidence review, cautious result interpretation, and JSON export. Install and
start it from inside `CapStone Project/`:

```powershell
python -m pip install -e ".[ui]"
streamlit run streamlit_app.py
```

The default heuristic mode runs locally and is recommended for a quick demonstration. Ollama,
OpenAI, SciFact-LoRA, scholarly APIs, and AI-text detection can be selected in the sidebar when
their respective dependencies and environment variables are configured. Confidence values in
the interface are explicitly presented as model signals, not correctness probabilities.

## 1. Base installation

Run from inside `CapStone Project/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
```

Dependency profiles are deliberately separated:

- `requirements.txt`: small, CPU-only base application.
- `requirements-rag.txt`: NumPy and Sentence Transformers.
- `requirements-lora.txt`: RAG plus Torch, Datasets, PEFT, and Accelerate.
- `requirements-binoculars.txt`: official Binoculars integration and its model stack.
- `requirements-torch-cuda.txt`: pinned CUDA 12.8 Torch wheel for this Windows/NVIDIA setup.

Keeping the large model stacks out of the base requirements makes installation and grading more
reliable, especially on Windows.

The application now loads `.env` automatically. Never commit `.env`; it is ignored by Git.

## 2. Basic offline analysis

```powershell
python run_claimguard.py `
  --input data/sample_input/sample_bad_paper.txt `
  --output outputs/sample_analysis.json `
  --claims-csv outputs/sample_claims.csv `
  --markdown-output outputs/sample_report.md
```

Analyze an RQ report:

```powershell
python run_claimguard.py `
  --input "Reports/NW2_RQ1_Report.pdf" `
  --output outputs/rq1_analysis.json `
  --markdown-output outputs/rq1_report.md
```

The Markdown report is intended for humans. The larger JSON preserves every prediction,
evidence chunk, confidence score, backend name, and API result for evaluation.

## 3. Scholarly APIs and full-text retrieval

Edit `.env`:

```dotenv
CLAIMGUARD_ENABLE_APIS=true
CROSSREF_MAILTO=your-real-email@example.com
OPENALEX_MAILTO=your-real-email@example.com
SEMANTIC_SCHOLAR_API_KEY=
UNPAYWALL_EMAIL=your-real-email@example.com
CLAIMGUARD_FETCH_FULL_TEXT=false
```

CrossRef and OpenAlex do not require API keys for normal polite use. A Semantic Scholar key is
optional but useful for rate limits. Enable bounded open-access PDF retrieval explicitly:

```powershell
python run_claimguard.py `
  --input "Reports/NW2_RQ1_Report.pdf" `
  --output outputs/rq1_api_analysis.json `
  --enable-apis `
  --fetch-full-text
```

The downloader accepts only HTTP(S) PDFs, limits downloads to 20 MB each, and fetches at most
three sources by default. Change `CLAIMGUARD_MAX_FULL_TEXT_SOURCES` if needed.

## 4. Embedding retrieval

Install the optional RAG dependencies:

```powershell
python -m pip install -r requirements-rag.txt
```

For the first model download, set:

```dotenv
CLAIMGUARD_USE_EMBEDDINGS=true
CLAIMGUARD_EMBEDDING_LOCAL_ONLY=false
CLAIMGUARD_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

After the model is cached, switch `CLAIMGUARD_EMBEDDING_LOCAL_ONLY=true` for reproducible
offline runs. ClaimGuard uses FAISS when available, embedding cosine similarity otherwise, and
deterministic lexical retrieval as the final fallback.

## 5. Claim verification backends

Every backend receives the same retrieved evidence and returns the same five labels:

- `supported`
- `partially_supported`
- `not_supported`
- `contradicted`
- `insufficient_evidence`

### Heuristic baseline

```powershell
python run_claimguard.py --input data/sample_input/sample_bad_paper.txt --output outputs/heuristic.json --verifier heuristic
```

This is the transparent offline baseline based on lexical coverage, negation, direction, and
explicit absence-of-evidence cues.

### Local Ollama model

Install Ollama separately, then:

```powershell
ollama pull qwen3:1.7b
ollama serve
```

Configure and run:

```dotenv
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:1.7b
```

```powershell
python run_claimguard.py --input data/sample_input/sample_bad_paper.txt --output outputs/ollama.json --verifier ollama
```

### OpenAI frontier model

ChatGPT subscriptions and API billing are separate. ChatGPT Plus does not automatically provide
API credits. Create an API project/key and configure API billing at
https://platform.openai.com/, then put the key only in your local `.env`:

```dotenv
OPENAI_API_KEY=your-key
OPENAI_MODEL=gpt-5.4-mini
# Optional when you need explicit dashboard attribution:
OPENAI_PROJECT_ID=
OPENAI_ORGANIZATION_ID=
```

Run:

```powershell
python run_claimguard.py --input data/sample_input/sample_bad_paper.txt --output outputs/openai.json --verifier openai
```

The implementation uses the OpenAI Responses API with a strict JSON schema and `store=false`.
API calls cost money. Keep benchmark inputs small and inspect usage in each verification's
metadata.

Run one minimal, sanitized connection and dashboard-attribution check:

```powershell
python run_openai_diagnostic.py
```

The output shows the OpenAI response ID, request ID, model, project/organization attribution,
and token usage without printing the API key. In the OpenAI Usage Dashboard, select the same
organization, clear the project selector to show all projects, and remember that dashboard time
ranges use UTC.

### SciFact LoRA adapter

After training Module 5, configure:

```dotenv
CLAIMGUARD_LORA_MODEL=outputs/scifact-lora
```

```powershell
python run_claimguard.py --input data/sample_input/sample_bad_paper.txt --output outputs/lora.json --verifier lora
```

## 6. Optional Module 4: AI-generated-text detection

The lightweight heuristic is useful only as a baseline:

```powershell
python run_ai_detection.py `
  --input "Reports/NW2_RQ1_Report.pdf" `
  --output outputs/ai_heuristic.json `
  --method heuristic
```

Install and run the ICML 2024 Binoculars integration:

```powershell
py -3.10 -m venv .venv-binoculars
.\.venv-binoculars\Scripts\python.exe -m pip install -r requirements-binoculars.txt
.\.venv-binoculars\Scripts\python.exe run_ai_detection.py `
  --input "Reports/NW2_RQ1_Report.pdf" `
  --output outputs/ai_binoculars.json `
  --method binoculars
```

The separate environment is intentional: the official implementation pins Transformers 4.31
and was tested with Python 3.9, whereas the main project uses a current Transformers release.
Its calibrated pair is `tiiuae/falcon-7b` plus `tiiuae/falcon-7b-instruct` (roughly 14 billion
parameters in total). It does not fit into an 8 GB RTX 3070 Ti; use a substantially larger GPU
or enough system RAM for CPU inference. A smaller custom pair changes the score distribution
and invalidates the published threshold unless it is recalibrated. AI-detection output is not
proof of authorship and must never be used as an automatic misconduct decision.

## 7. Optional Module 5: SciFact LoRA training

Install training dependencies:

```powershell
python -m pip install -r requirements-torch-cuda.txt
python -m pip install -r requirements-lora.txt
```

Train and evaluate a DeBERTa-v3-base sequence classifier with LoRA:

```powershell
python train_scifact_lora.py `
  --base-model microsoft/deberta-v3-base `
  --output outputs/scifact-lora `
  --epochs 3 `
  --batch-size 4 `
  --gradient-accumulation 4
```

The script downloads the official `allenai/scifact` claims and corpus configurations, joins
claims to evidence abstracts, trains only LoRA adapters, evaluates Accuracy and Macro-F1, and
writes `training_report.json`. SciFact is CC BY-NC 2.0; review its license before use.

The completed adapter in this workspace is `outputs/scifact-lora`, trained from
`distilbert-base-uncased` on 1,261 training and 450 validation pairs. It reached 0.409 validation
Accuracy and 0.353 Macro-F1. See `docs/FINAL_RESULTS.md` for transfer results and caveats.

Training requires model downloads and substantially more compute than the base project. If GPU
memory is limited, reduce batch size or choose a smaller compatible encoder and adjust
`--target-modules`. The default `auto` setting detects the attention query/value projections
without wrapping the classification head. For a
quick real smoke run on the cached smaller model, add `--base-model distilbert-base-uncased
--max-train-samples 200 --max-eval-samples 100 --epochs 1`.

## 8. Evaluation and model comparison

Evaluate Module 1 claim types and citation-needed flags separately:

```powershell
python run_claim_evaluation.py `
  --benchmark data/benchmark/rq_claim_annotations.csv `
  --output outputs/rq_claim_evaluation.json
```

Evaluate Module 2 reference-field extraction offline:

```powershell
python run_reference_evaluation.py `
  --benchmark data/benchmark/reference_parsing_benchmark.csv `
  --output outputs/reference_evaluation.json
```

The included benchmark now contains 30 labeled examples, six for each verification label:

```powershell
python run_evaluation.py `
  --benchmark data/benchmark/claimguard_benchmark.csv `
  --output outputs/evaluation_heuristic.json `
  --verifier heuristic
```

Compare baseline, local, and frontier models on exactly the same cases:

```powershell
python run_model_comparison.py `
  --benchmark data/benchmark/claimguard_benchmark.csv `
  --output outputs/model_comparison.json `
  --markdown-output outputs/model_comparison.md `
  --verifiers heuristic,ollama,openai
```

The report includes per-label Precision/Recall/F1, Macro-F1, Micro-F1, confusion matrices,
latency, qualitative examples, and backend errors. The current offline heuristic result is
approximately 0.90 Accuracy and 0.90 Macro-F1. The dataset is still a teaching benchmark, not a
deployment-quality estimate.

The real-RQ annotation file contains 50 manually reviewed sentences, ten from each RQ report.
It is deliberately kept separate from the synthetic regression benchmark. Current measured
results and the exact experimental status are summarized in `docs/FINAL_RESULTS.md`.

## 9. Optional Module 6: comparison with existing tools

Run the benchmark through an existing tool such as Scite or SemanticCite. Record one row per
case using `data/benchmark/external_tool_predictions_template.csv` and the columns
`case_id,predicted,notes`.

Then compare all exported predictions:

```powershell
python run_tool_comparison.py `
  --benchmark data/benchmark/claimguard_benchmark.csv `
  --tool ClaimGuard=outputs/evaluation_heuristic.json `
  --tool ExistingTool=data/benchmark/existing_tool_predictions.csv `
  --output outputs/tool_comparison.json
```

This produces a shared leaderboard, coverage, Accuracy, Macro/Micro-F1, per-label metrics, and
error lists. External tools often require manual use or their own accounts; ClaimGuard therefore
uses an explicit prediction import rather than pretending to automate an unavailable API.

## 10. Tests

```powershell
pytest
```

The suite covers citation formats, section-aware classification, severity/context linking,
reference parsing and venue extraction, fuzzy matching, RAG retrieval, shared model output
schemas, AI-detection safeguards, evaluation, tool comparison, Markdown output, and full-pipeline
smoke tests.

Report, presentation, and human-annotation checklists live in `docs/`. They deliberately contain
placeholders for empirical results: run the local/frontier/external-tool experiments before
claiming those results in the submission.

## Architecture

```mermaid
flowchart TD
    A[PDF or TXT] --> B[Parser and PDF cleanup]
    B --> C[Section-aware sentence processing]
    C --> D[Claim classifier and citation linker]
    B --> E[Reference parser]
    E --> F[CrossRef / Semantic Scholar / OpenAlex]
    F --> G[Abstracts and optional OA full text]
    G --> H[Chunking]
    H --> I[Lexical / embeddings / FAISS retrieval]
    D --> J[Heuristic / Ollama / OpenAI / LoRA verifier]
    I --> J
    B --> K[Heuristic / Binoculars AI detection]
    J --> L[JSON + CSV + Markdown]
    K --> L
    M[30-case benchmark] --> N[Model and external-tool comparisons]
```

## Limitations and ethics

- PDF extraction is never perfect, especially for scanned or multi-column documents.
- The baseline claim classifier is heuristic; methods and original results can still be
  misclassified.
- Bibliographic API matches depend on metadata quality and service availability.
- Abstracts may not contain enough information to verify detailed claims.
- LLM verifier outputs are nondeterministic and can be wrong.
- AI-generated-text detection is unreliable for edited, paraphrased, short, and non-English text.
- Confidence values are calibration signals, not probabilities of misconduct.
- Human review is mandatory before grading, publication, or integrity decisions.
