from claimguard.claims.classifier import ClaimClassifier


def test_claim_classifier_flags_uncited_factual_claim() -> None:
    classifier = ClaimClassifier()

    claim = classifier.classify_sentence(
        "Neural networks improved image classification accuracy in 2021.",
        sentence_index=0,
    )

    assert claim.claim_type == "factual_claim"
    assert claim.missing_citation is True


def test_claim_classifier_detects_method_and_opinion() -> None:
    classifier = ClaimClassifier()

    method = classifier.classify_sentence("We trained a model on 100 documents.", 0)
    opinion = classifier.classify_sentence("The results are probably exciting.", 1)

    assert method.claim_type == "methodological_statement"
    assert opinion.claim_type == "opinion_or_interpretation"
    assert method.classification_reason
    assert opinion.classification_confidence > 0


def test_claim_classifier_detects_definition_and_cited_factual_claim() -> None:
    classifier = ClaimClassifier()

    definition = classifier.classify_sentence(
        "Gradient descent is an optimization method.", 0
    )
    factual = classifier.classify_sentence(
        "Prior studies showed that augmentation improved accuracy (Smith et al., 2020).",
        1,
    )

    assert definition.claim_type == "background_or_definition"
    assert definition.missing_citation is False
    assert factual.claim_type == "factual_claim"
    assert factual.missing_citation is False
    assert factual.citations[0].author_hint == "Smith"
