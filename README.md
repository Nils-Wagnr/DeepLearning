# Deep Learning

Dieses Repository dokumentiert die praktischen Arbeiten aus dem Modul **Deep
Learning**. Im Mittelpunkt stehen fünf aufeinander aufbauende Research Questions
(RQ), die von klassischen neuronalen Netzen über CNNs und Sequenzmodelle bis zu
Pretraining und Retrieval-Augmented Generation (RAG) reichen.

Die Experimente sind als Jupyter Notebooks umgesetzt und enthalten neben dem
Code auch Auswertungen, Visualisierungen und die jeweiligen Ergebnisse.

## Inhalte

| Ordner | Thema | Schwerpunkte |
| --- | --- | --- |
| [RQ1 – Woche 2](<RQ1%20(Woche%202)/>) | Regularisierung von MLPs | L1/L2, Dropout, Batch Normalization, Early Stopping und Overfitting auf MNIST |
| [RQ2 – Woche 4](<RQ2%20(Woche%204)/>) | Robustheit von Bildklassifikatoren | Vergleich von MLP und CNN bei systematischen Bildstörungen auf MNIST |
| [RQ3 – Woche 6](<RQ3%20(Woche%206)/>) | Sequenzmodelle für Text | Vergleich von TextCNN, Vanilla RNN und LSTM bei unterschiedlichen Sequenzlängen |
| [RQ4 – Woche 8](<RQ4%20(Woche%208)/>) | Training from Scratch vs. Pretraining | LSTM, BERT Fine-Tuning und LLM Prompting bei verschiedenen Datenmengen |
| [RQ5 – Woche 10](<RQ5%20(Woche%2010)/>) | Retrieval-Augmented Generation | Chunking, Embeddings, FAISS-Retrieval, Cross-Encoder-Reranking und Antwortqualität |

Das [Capstone Project](<CapStone%20Project/>) ist ein eigenständiger Projektteil
und besitzt eine separate README mit eigener Installation und Dokumentation.

## Repository-Struktur

```text
DeepLearning/
├── RQ1 (Woche 2)/       # Regularisierung und Modellgröße
├── RQ2 (Woche 4)/       # MLP/CNN und Bildperturbationen
├── RQ3 (Woche 6)/       # TextCNN, RNN und LSTM
├── RQ4 (Woche 8)/       # LSTM, BERT und LLM Prompting
├── RQ5 (Woche 10)/      # RAG, Chunking und Reranking
├── CapStone Project/    # Separates Abschlussprojekt
└── README.md
```

In den RQ-Ordnern befinden sich die ausführbaren Notebooks sowie – je nach
Aufgabe – Datensätze, CSV-Auswertungen und erzeugte Abbildungen.

## Voraussetzungen

- Python 3.10 oder neuer
- JupyterLab oder Jupyter Notebook
- Optional: CUDA-fähige GPU für rechenintensive Experimente

Die benötigten Bibliotheken unterscheiden sich je nach Notebook. Zu den
wichtigsten Paketen gehören PyTorch, torchvision, NumPy, pandas, Matplotlib,
scikit-learn, Hugging Face Transformers/Datasets, sentence-transformers und
FAISS.

## Schnellstart

Repository klonen und eine virtuelle Umgebung erstellen:

```bash
git clone <repository-url>
cd DeepLearning
python -m venv .venv
```

Virtuelle Umgebung aktivieren:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux/macOS
source .venv/bin/activate
```

Grundlegende Abhängigkeiten installieren:

```bash
pip install jupyter torch torchvision numpy pandas matplotlib scipy scikit-learn
```

Für die späteren Aufgaben werden zusätzliche Pakete benötigt:

```bash
pip install datasets evaluate gensim transformers sentence-transformers faiss-cpu nltk
```

Anschließend Jupyter starten und das gewünschte Notebook öffnen:

```bash
jupyter lab
```

## Hinweise zur Ausführung

- Die Notebooks sollten innerhalb ihres jeweiligen RQ-Ordners ausgeführt
  werden, da Daten und Ergebnisse teilweise über relative Pfade geladen werden.
- Einige Datensätze und Modelle werden beim ersten Start automatisch
  heruntergeladen; dafür ist eine Internetverbindung erforderlich.
- Laufzeit und Speicherbedarf steigen insbesondere bei BERT-, LLM- und
  RAG-Experimenten deutlich an.
- Bereits erzeugte Ergebnisdateien und Diagramme ermöglichen einen Einblick in
  die Resultate, ohne alle Experimente erneut auszuführen.

## Technologien

Python · Jupyter · PyTorch · Hugging Face · scikit-learn · FAISS · Matplotlib
