# ClaimGuard annotation guide

Use this guide to turn the synthetic benchmark into defensible capstone evaluation data.

## Unit of annotation

Annotate one atomic claim and its cited evidence. Split sentences containing several independent
claims before annotation. Keep the original document and page number in the notes.

## Module 1 labels

- `factual_claim`: externally verifiable assertion.
- `methodological_statement`: what the current authors did.
- `opinion_or_interpretation`: judgment, recommendation, or hedged interpretation.
- `background_or_definition`: definition or framing statement.
- `non_claim`: heading, fragment, metadata, or other non-proposition.

Set `citation_needed=true` only when an external factual assertion requires support. Original
method descriptions and results normally do not require an external citation.

## Module 3 labels

- `supported`: evidence directly establishes the complete claim.
- `partially_supported`: correct topic/direction, but scope, strength, population, or conditions
  are not fully established.
- `not_supported`: relevant source, but the claimed result is not established.
- `contradicted`: evidence explicitly establishes an incompatible result.
- `insufficient_evidence`: retrieved material is absent, irrelevant, or too incomplete to judge.

## Procedure

1. Select at least 30–50 claims from RQ reports and deliberately bad examples.
2. Both team members annotate independently.
3. Record disagreements before discussion.
4. Resolve disagreements and document the final rationale.
5. Keep the gold labels fixed before running the compared systems.
6. Report inter-annotator agreement and all exclusions.

Do not tune rules or prompts on the final test set. Use a separate development subset.
