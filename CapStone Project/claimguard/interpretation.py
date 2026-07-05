"""Human-readable interpretations for ClaimGuard reports.

The functions in this module deliberately do not make new model predictions. They
translate existing pipeline signals into cautious review guidance that can be used
by the CLI, notebooks, or the Streamlit frontend.
"""

from __future__ import annotations

from typing import Any


STATUS_LABELS = {
    "supported": "Gestützt",
    "partially_supported": "Teilweise gestützt",
    "not_supported": "Nicht gestützt",
    "contradicted": "Widersprüchlich",
    "insufficient_evidence": "Unzureichende Evidenz",
}

CLAIM_TYPE_LABELS = {
    "factual_claim": "Faktische Aussage",
    "methodological_statement": "Methodische Aussage",
    "opinion_or_interpretation": "Meinung oder Interpretation",
    "background_or_definition": "Hintergrund oder Definition",
    "non_claim": "Keine prüfbare Aussage",
}


def confidence_label(value: Any) -> str:
    """Describe confidence without presenting it as a correctness probability."""

    try:
        confidence = float(value)
    except (TypeError, ValueError):
        confidence = 0.0
    if confidence >= 0.8:
        return "starkes Modellsignal"
    if confidence >= 0.55:
        return "mittleres Modellsignal"
    if confidence >= 0.3:
        return "schwaches Modellsignal"
    return "sehr schwaches Modellsignal"


def interpret_verification(verification: dict[str, Any]) -> dict[str, str]:
    """Turn one source-verification result into careful German guidance."""

    status = str(verification.get("status", "insufficient_evidence"))
    interpretations = {
        "supported": (
            "Die gefundene Evidenz passt inhaltlich zur Aussage.",
            "Quelle und Originalkontext trotzdem kurz prüfen; das Ergebnis ist kein Wahrheitsbeweis.",
        ),
        "partially_supported": (
            "Die Quelle stützt einen Teil der Aussage, aber Umfang, Stärke oder Kontext passen nicht vollständig.",
            "Aussage enger formulieren oder eine zusätzliche, passendere Quelle ergänzen.",
        ),
        "not_supported": (
            "In der gefundenen Evidenz lässt sich die Aussage nicht ausreichend belegen.",
            "Originalquelle prüfen und entweder die Formulierung korrigieren oder eine tragfähige Quelle suchen.",
        ),
        "contradicted": (
            "Die gefundene Evidenz enthält Hinweise, die der Aussage entgegenstehen.",
            "Aussage und Originalquelle manuell vergleichen; vor Abgabe nicht unverändert übernehmen.",
        ),
        "insufficient_evidence": (
            "Für eine belastbare Bewertung wurde zu wenig passende Evidenz gefunden.",
            "Quelle, Volltextzugriff und Zitationszuordnung prüfen; daraus keine inhaltliche Schlussfolgerung ziehen.",
        ),
    }
    meaning, recommendation = interpretations.get(status, interpretations["insufficient_evidence"])
    return {
        "label": STATUS_LABELS.get(status, status.replace("_", " ").title()),
        "meaning": meaning,
        "recommendation": recommendation,
        "signal": confidence_label(verification.get("confidence", 0.0)),
    }


def claim_recommendation(
    claim: dict[str, Any], verification: dict[str, Any] | None = None
) -> str:
    """Return the most useful next review action for a claim."""

    if claim.get("missing_citation"):
        return "Externe faktische Aussage: Zitation ergänzen oder als eigene Interpretation kenntlich machen."
    if verification:
        return interpret_verification(verification)["recommendation"]
    if claim.get("claim_type") == "factual_claim":
        return "Zitationszuordnung und Quelle bei der manuellen Endkontrolle prüfen."
    return "Kein unmittelbarer Quellenkonflikt erkannt; bei der Endredaktion im Kontext prüfen."


def interpret_report(report: dict[str, Any]) -> dict[str, Any]:
    """Summarize the report as review priority, explanation, and next steps."""

    claims = report.get("claims") or report.get("module_1", {}).get("claims", [])
    verifications = report.get("claim_verification", [])
    missing = [claim for claim in claims if claim.get("missing_citation")]
    high_missing = [claim for claim in missing if claim.get("flag_severity") == "high"]
    counts: dict[str, int] = {}
    for item in verifications:
        status = str(item.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1

    conflicts = counts.get("contradicted", 0) + counts.get("not_supported", 0)
    open_checks = counts.get("partially_supported", 0) + counts.get("insufficient_evidence", 0)

    if conflicts or high_missing:
        level = "Erhöhter Prüfbedarf"
        tone = "danger"
        summary = (
            "Mindestens eine Aussage sollte vor der Abgabe gezielt mit der Originalquelle "
            "abgeglichen werden."
        )
    elif missing or open_checks:
        level = "Mittlerer Prüfbedarf"
        tone = "warning"
        summary = "Es gibt offene Zitations- oder Evidenzfragen, aber keinen starken Konflikthinweis."
    else:
        level = "Geringer Prüfbedarf"
        tone = "success"
        summary = "Die automatische Prüfung hat keine auffälligen Quellenkonflikte gefunden."

    actions: list[str] = []
    if conflicts:
        actions.append(f"{conflicts} nicht gestützte oder widersprüchliche Aussage(n) manuell prüfen.")
    if missing:
        actions.append(f"Für {len(missing)} zitationspflichtige Aussage(n) eine Quelle ergänzen.")
    if open_checks:
        actions.append(f"Bei {open_checks} offenen Fall/Fällen Evidenz oder Formulierung nachschärfen.")
    if not actions:
        actions.append("Stichprobenartig Originalquellen prüfen und anschließend final redigieren.")

    return {
        "level": level,
        "tone": tone,
        "summary": summary,
        "actions": actions,
        "counts": {
            "conflicts": conflicts,
            "missing_citations": len(missing),
            "open_checks": open_checks,
        },
        "warning": (
            "Die Bewertung priorisiert Prüfstellen. Sie beweist weder wissenschaftliche "
            "Korrektheit noch Fehlverhalten; Konfidenzen sind Modellsignale, keine "
            "Wahrscheinlichkeiten dafür, dass eine Aussage wahr oder falsch ist."
        ),
    }
