"""Load the Wikipedia DL corpus and evaluation questions.

This module provides a simple interface to load the pre-built corpus
of 20 Wikipedia articles on Deep Learning topics and 40 evaluation
questions at three difficulty levels.

Usage:
    from load_corpus import load_corpus
    documents, questions = load_corpus()

    # Access a document
    print(documents[0]["title"])   # "Artificial intelligence"
    print(documents[0]["text"][:200])

    # Access a question
    print(questions[0]["question"])
    print(questions[0]["answer"])
    print(questions[0]["difficulty"])  # "easy", "medium", or "hard"
"""
import json
from pathlib import Path


def load_corpus() -> tuple[list[dict], list[dict]]:
    """Load documents and evaluation questions.

    Returns:
        documents: list of dicts with keys:
            - 'id': str (e.g., "article_01")
            - 'title': str (Wikipedia article title)
            - 'url': str (Wikipedia URL)
            - 'text': str (full article text)
            - 'word_count': int
        questions: list of dicts with keys:
            - 'id': str (e.g., "q01")
            - 'question': str
            - 'answer': str (ground-truth answer)
            - 'source_article': str (article id)
            - 'source_article_title': str
            - 'difficulty': str ("easy", "medium", or "hard")
    """
    corpus_dir = Path(__file__).parent

    corpus_path = corpus_dir / "wikipedia_dl_corpus.json"
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Corpus file not found at {corpus_path}. "
            "Run 'python build_corpus.py' first to download the articles."
        )

    questions_path = corpus_dir / "wikipedia_dl_questions.json"
    if not questions_path.exists():
        raise FileNotFoundError(
            f"Questions file not found at {questions_path}."
        )

    with open(corpus_path, "r", encoding="utf-8") as f:
        documents = json.load(f)

    with open(questions_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    return documents, questions


def print_summary() -> None:
    """Print a summary of the corpus and questions."""
    documents, questions = load_corpus()

    total_words = sum(d["word_count"] for d in documents)
    avg_words = total_words / len(documents) if documents else 0

    difficulty_counts: dict[str, int] = {}
    for q in questions:
        diff = q["difficulty"]
        difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1

    print("=" * 60)
    print("Wikipedia Deep Learning Corpus - Summary")
    print("=" * 60)
    print(f"\nArticles:          {len(documents)}")
    print(f"Total word count:  {total_words:,}")
    print(f"Average words:     {avg_words:,.0f}")
    print(f"Shortest article:  {min(d['word_count'] for d in documents):,} words")
    print(f"Longest article:   {max(d['word_count'] for d in documents):,} words")
    print(f"\nQuestions:         {len(questions)}")
    for diff in ["easy", "medium", "hard"]:
        count = difficulty_counts.get(diff, 0)
        print(f"  {diff:8s}:       {count}")

    print(f"\nArticles:")
    for doc in documents:
        print(f"  {doc['id']}: {doc['title']} ({doc['word_count']:,} words)")


if __name__ == "__main__":
    print_summary()
