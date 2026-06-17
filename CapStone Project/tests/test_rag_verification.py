from claimguard.claims.classifier import ClaimClassifier
from claimguard.models import Reference
from claimguard.rag.retriever import EvidenceRetriever, build_evidence_passages, chunk_text
from claimguard.rag.verifier import ClaimVerifier


def test_chunk_text_creates_overlapping_chunks_for_long_passages() -> None:
    text = " ".join(f"token{i}" for i in range(130))

    chunks = chunk_text(text, max_words=40, overlap_words=10)

    assert len(chunks) > 1
    assert "token30" in chunks[0]
    assert "token30" in chunks[1]


def test_retriever_returns_top_k_ranked_evidence() -> None:
    references = [
        Reference(raw_text="[1] Smith, A. (2020). Medical imaging.", index="1", title="Medical imaging", year=2020),
        Reference(raw_text="[2] Brown, B. (2021). Soil moisture.", index="2", title="Soil moisture", year=2021),
    ]
    evidence_text = """
[1] Deep learning improved image classification accuracy on medical imaging datasets compared with baseline models.
[2] Soil moisture measurements were collected from alpine forests.
"""
    passages = build_evidence_passages(evidence_text, references)
    retriever = EvidenceRetriever(passages)

    results = retriever.retrieve(
        "Deep learning improved image classification accuracy.",
        reference_indices={"1"},
        top_k=2,
    )

    assert len(results) <= 2
    assert results[0].reference_index == "1"
    assert results[0].score > 0.4
    assert results[0].retrieval_method in {"lexical", "embedding", "faiss"}


def test_verifier_produces_clear_support_labels() -> None:
    references = [
        Reference(raw_text="[1] Smith, A. (2020). Medical imaging.", index="1", authors=["Smith"], year=2020),
        Reference(raw_text="[2] Brown, B. (2021). Language models.", index="2", authors=["Brown"], year=2021),
        Reference(raw_text="[3] Clark, C. (2022). Citation checking.", index="3", authors=["Clark"], year=2022),
    ]
    evidence_text = """
[1] Deep learning improved image classification accuracy on medical imaging datasets compared with baseline models.
[2] Large language models can hallucinate unsupported facts and do not eliminate errors.
[3] The source discusses citation checking but does not test student grading outcomes.
"""
    passages = build_evidence_passages(evidence_text, references)
    retriever = EvidenceRetriever(passages)
    classifier = ClaimClassifier()
    verifier = ClaimVerifier()

    supported = verifier.verify_claim(
        classifier.classify_sentence("Deep learning improved image classification accuracy [1].", 0),
        references,
        retriever,
    )
    contradicted = verifier.verify_claim(
        classifier.classify_sentence("Large language models eliminate all hallucinations [2].", 1),
        references,
        retriever,
    )
    not_supported = verifier.verify_claim(
        classifier.classify_sentence("Citation checking improves grading outcomes [3].", 2),
        references,
        retriever,
    )
    insufficient = verifier.verify_claim(
        classifier.classify_sentence("Citation checking improves grading outcomes.", 3),
        references,
        retriever,
    )

    assert supported.status == "supported"
    assert contradicted.status == "contradicted"
    assert not_supported.status == "not_supported"
    assert insufficient.status == "insufficient_evidence"
    assert supported.confidence > not_supported.confidence

