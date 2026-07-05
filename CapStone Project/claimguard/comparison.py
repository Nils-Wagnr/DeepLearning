"""Utilities for comparing ClaimGuard verifier reports on the same document."""

from __future__ import annotations

from typing import Any


def compare_reports(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Align verifier outputs by claim and summarize agreements and differences."""

    backends = list(reports)
    claims: dict[int, str] = {}
    indexed_results: dict[str, dict[int, dict[str, Any]]] = {}

    for backend, report in reports.items():
        for claim in report.get("claims", []):
            index = claim.get("sentence_index")
            if isinstance(index, int):
                claims.setdefault(index, str(claim.get("sentence", "")))
        indexed_results[backend] = {
            item["claim_index"]: item
            for item in report.get("claim_verification", [])
            if isinstance(item.get("claim_index"), int)
        }

    claim_indices = sorted(
        {
            index
            for results in indexed_results.values()
            for index in results
        }
    )
    rows: list[dict[str, Any]] = []
    agreements = 0
    disagreements = 0
    incomplete = 0
    backend_errors = 0

    for index in claim_indices:
        model_results: dict[str, dict[str, Any]] = {}
        valid_statuses: list[str] = []
        for backend in backends:
            verification = indexed_results.get(backend, {}).get(index)
            if verification is None:
                model_results[backend] = {
                    "status": None,
                    "confidence": None,
                    "rationale": "Für diese Aussage liegt kein Prüfergebnis vor.",
                    "model": None,
                    "latency_ms": None,
                    "error": None,
                }
                continue
            error = (verification.get("metadata") or {}).get("backend_error")
            if error:
                backend_errors += 1
            else:
                valid_statuses.append(str(verification.get("status", "")))
            model_results[backend] = {
                "status": verification.get("status"),
                "confidence": verification.get("confidence"),
                "rationale": verification.get("rationale", ""),
                "model": verification.get("model"),
                "latency_ms": verification.get("latency_ms"),
                "error": str(error) if error else None,
            }

        if len(valid_statuses) == len(backends) and len(set(valid_statuses)) == 1:
            agreement = "agreement"
            agreements += 1
        elif len(valid_statuses) >= 2 and len(set(valid_statuses)) > 1:
            agreement = "disagreement"
            disagreements += 1
        else:
            agreement = "incomplete"
            incomplete += 1
        rows.append(
            {
                "claim_index": index,
                "sentence": claims.get(index, ""),
                "agreement": agreement,
                "models": model_results,
            }
        )

    backend_summary: dict[str, dict[str, Any]] = {}
    for backend in backends:
        results = indexed_results.get(backend, {}).values()
        statuses: dict[str, int] = {}
        errors = 0
        latency_ms = 0
        model_calls = 0
        models: set[str] = set()
        for item in results:
            error = (item.get("metadata") or {}).get("backend_error")
            if error:
                errors += 1
                continue
            status = str(item.get("status", "unknown"))
            statuses[status] = statuses.get(status, 0) + 1
            if item.get("latency_ms") is not None:
                model_calls += 1
                latency_ms += int(item.get("latency_ms") or 0)
            if item.get("model"):
                models.add(str(item["model"]))
        backend_summary[backend] = {
            "status_counts": statuses,
            "errors": errors,
            "model_calls": model_calls,
            "latency_ms": latency_ms,
            "models": sorted(models),
        }

    return {
        "backends": backends,
        "summary": {
            "models": len(backends),
            "claims_compared": len(rows),
            "agreements": agreements,
            "disagreements": disagreements,
            "incomplete": incomplete,
            "backend_errors": backend_errors,
        },
        "backend_summary": backend_summary,
        "rows": rows,
        "warning": (
            "Übereinstimmung misst nur, ob Modelle dasselbe Label vergeben. Ohne manuell "
            "geprüfte Ground-Truth-Labels lässt sich daraus keine Accuracy und kein bestes "
            "Modell ableiten."
        ),
    }
