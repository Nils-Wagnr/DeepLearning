"""Interactive ClaimGuard frontend.

Run from the project directory with:
    streamlit run streamlit_app.py
"""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from claimguard.comparison import compare_reports
from claimguard.interpretation import (
    CLAIM_TYPE_LABELS,
    STATUS_LABELS,
    claim_recommendation,
    confidence_label,
    interpret_report,
    interpret_verification,
)
from claimguard.pipeline import analyze_document


PROJECT_ROOT = Path(__file__).resolve().parent
SAMPLES = {
    "Problematischer Beispieltext": PROJECT_ROOT / "data/sample_input/sample_bad_paper.txt",
    "Unauffälliger Beispieltext": PROJECT_ROOT / "data/sample_input/sample_paper.txt",
}

STATUS_ICONS = {
    "supported": "✅",
    "partially_supported": "🟡",
    "not_supported": "🟠",
    "contradicted": "🔴",
    "insufficient_evidence": "⚪",
}

BACKEND_LABELS = {
    "heuristic": "Heuristik",
    "ollama": "Ollama",
    "lora": "SciFact-LoRA",
    "openai": "OpenAI",
}


def _configure_page() -> None:
    st.set_page_config(
        page_title="ClaimGuard · Quellenprüfung",
        page_icon="🛡️",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        .block-container {max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem;}
        [data-testid="stMetric"] {background: rgba(120,120,120,.07); border: 1px solid rgba(120,120,120,.18); padding: 1rem; border-radius: .8rem;}
        .cg-hero {padding: 1.35rem 1.5rem; border-radius: 1rem; background: linear-gradient(120deg, rgba(45,108,223,.16), rgba(39,174,96,.10)); border: 1px solid rgba(80,120,180,.22); margin-bottom: 1.25rem;}
        .cg-hero h1 {margin: 0 0 .25rem 0; font-size: 2.15rem;}
        .cg-hero p {margin: 0; opacity: .82;}
        .cg-note {font-size: .9rem; opacity: .78;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_settings() -> tuple[str, bool, str | None]:
    with st.sidebar:
        st.header("Analyse konfigurieren")
        verifier = st.selectbox(
            "Prüfmethode",
            options=["heuristic", "ollama", "openai", "lora"],
            format_func={
                "heuristic": "Heuristik · lokal & schnell",
                "ollama": "Ollama · lokales LLM",
                "openai": "OpenAI · API",
                "lora": "SciFact-LoRA · lokal",
            }.get,
            help="Die Heuristik ist für eine schnelle, reproduzierbare Demo empfohlen.",
        )
        enable_apis = st.toggle(
            "Wissenschaftliche APIs verwenden",
            value=False,
            help="Validiert Literaturangaben über konfigurierte Dienste. Benötigt Internetzugriff.",
        )
        run_ai_detection = st.toggle(
            "KI-Text-Indikator",
            value=False,
            help="Optionaler, unzuverlässiger Indikator – niemals als Autorschaftsnachweis verwenden.",
        )
        ai_method = None
        if run_ai_detection:
            ai_method = st.selectbox(
                "Methode für KI-Text",
                options=["heuristic", "binoculars"],
                format_func=lambda value: "Heuristik" if value == "heuristic" else "Binoculars",
            )
        if verifier == "openai":
            st.warning("Dieser Modus kann API-Kosten verursachen und benötigt OPENAI_API_KEY.")
        elif verifier == "ollama":
            st.info("Ollama muss lokal laufen; Modell und URL kommen aus der .env-Datei.")
        elif verifier == "lora":
            st.info("Der konfigurierte SciFact-LoRA-Adapter wird lokal geladen.")
        st.divider()
        st.caption("ClaimGuard ist ein Triage-Werkzeug. Jede Markierung braucht menschliche Prüfung.")
    return verifier, enable_apis, ai_method


def _input_area() -> tuple[str | None, bytes | None, str | None]:
    st.subheader("1 · Dokument auswählen")
    source = st.radio(
        "Eingabeart",
        ["Beispiel", "Datei hochladen", "Text einfügen"],
        horizontal=True,
        label_visibility="collapsed",
    )
    if source == "Beispiel":
        sample_name = st.selectbox("Beispieldokument", list(SAMPLES))
        return str(SAMPLES[sample_name]), None, sample_name
    if source == "Datei hochladen":
        upload = st.file_uploader("PDF- oder TXT-Datei", type=["pdf", "txt"])
        if upload is None:
            return None, None, None
        return upload.name, upload.getvalue(), upload.name

    text = st.text_area(
        "Text des Dokuments",
        height=240,
        placeholder=(
            "Füge hier den Text einschließlich Literaturverzeichnis ein. "
            "Optional können nach ‚Evidence Passages‘ Evidenztexte folgen."
        ),
    )
    if not text.strip():
        return None, None, None
    return "eingefuegter_text.txt", text.encode("utf-8"), "Eingefügter Text"


def _run_analysis(
    path_or_name: str,
    content: bytes | None,
    display_name: str,
    verifier: str,
    enable_apis: bool,
    ai_method: str | None,
) -> dict[str, Any]:
    if content is None:
        analysis_path = Path(path_or_name)
        report = analyze_document(
            analysis_path,
            enable_apis=enable_apis,
            verifier=verifier,
            ai_detection=ai_method,
        )
    else:
        suffix = Path(path_or_name).suffix.lower()
        if suffix not in {".txt", ".pdf"}:
            suffix = ".txt"
        with tempfile.TemporaryDirectory(prefix="claimguard-") as directory:
            analysis_path = Path(directory) / f"document{suffix}"
            analysis_path.write_bytes(content)
            report = analyze_document(
                analysis_path,
                enable_apis=enable_apis,
                verifier=verifier,
                ai_detection=ai_method,
            )
    report["input_path"] = display_name
    return report


def _analysis_signature(
    path_or_name: str | None,
    content: bytes | None,
    verifier: str,
    enable_apis: bool,
    ai_method: str | None,
) -> tuple[str, str, bool, str | None]:
    """Identify the exact input and settings represented by a displayed report."""

    if content is not None:
        input_id = hashlib.sha256(content).hexdigest()
    else:
        input_id = str(Path(path_or_name).resolve()) if path_or_name else ""
    return input_id, verifier, enable_apis, ai_method


def _run_comparison(
    path_or_name: str,
    content: bytes | None,
    display_name: str,
    backends: list[str],
    enable_apis: bool,
    existing_report: dict[str, Any] | None,
    existing_signature: tuple[str, str, bool, str | None] | None,
    progress: Any,
) -> dict[str, dict[str, Any]]:
    """Run selected verifiers against one input, reusing a matching current report."""

    input_id = _analysis_signature(path_or_name, content, "heuristic", enable_apis, None)[0]
    reports: dict[str, dict[str, Any]] = {}

    def analyze_all(analysis_path: str) -> None:
        for backend in backends:
            can_reuse = bool(
                existing_report
                and existing_signature
                and existing_signature[0] == input_id
                and existing_signature[1] == backend
                and existing_signature[2] == enable_apis
            )
            if can_reuse:
                progress.write(f"{BACKEND_LABELS[backend]}: vorhandenen Bericht wiederverwendet.")
                reports[backend] = existing_report
                continue
            progress.write(f"{BACKEND_LABELS[backend]} wird ausgeführt …")
            report = analyze_document(
                analysis_path,
                enable_apis=enable_apis,
                verifier=backend,
                ai_detection=None,
            )
            report["input_path"] = display_name
            reports[backend] = report

    if content is None:
        analyze_all(path_or_name)
    else:
        suffix = Path(path_or_name).suffix.lower()
        if suffix not in {".txt", ".pdf"}:
            suffix = ".txt"
        with tempfile.TemporaryDirectory(prefix="claimguard-comparison-") as directory:
            analysis_path = Path(directory) / f"document{suffix}"
            analysis_path.write_bytes(content)
            analyze_all(str(analysis_path))
    return reports


def _backend_summary(report: dict[str, Any]) -> None:
    """Make it obvious whether the selected verifier was actually executed."""

    configuration = report.get("configuration", {})
    selected = str(configuration.get("verifier", "heuristic"))
    verifications = report.get("claim_verification", [])
    models = sorted({str(item.get("model")) for item in verifications if item.get("model")})
    errors = [
        str((item.get("metadata") or {}).get("backend_error"))
        for item in verifications
        if (item.get("metadata") or {}).get("backend_error")
    ]
    calls = [item for item in verifications if item.get("latency_ms") is not None]

    st.markdown(
        f"**Verwendete Prüfmethode:** `{selected}`"
        + (f" · **Modell:** `{', '.join(models)}`" if models else "")
    )
    if errors:
        st.error(
            "Das ausgewählte Backend konnte nicht ausgeführt werden. Der Bericht enthält an "
            f"diesen Stellen keine Modellbewertung. Ursache: {errors[0]}"
        )
    elif selected != "heuristic" and calls:
        st.success(
            f"Backend tatsächlich ausgeführt: {len(calls)} Modellaufruf/-aufrufe mit "
            f"{sum(int(item.get('latency_ms') or 0) for item in calls)} ms Gesamtlatenz."
        )
    elif selected != "heuristic":
        st.warning(
            "Das ausgewählte Modell wurde nicht aufgerufen, weil für keine zitierte Aussage "
            "ausreichend relevante Evidenz gefunden wurde."
        )
    else:
        st.caption("Die Quellenbewertung wurde mit der lokalen, deterministischen Heuristik erstellt.")


def _overview(report: dict[str, Any]) -> None:
    summary = report.get("summary", {})
    interpretation = interpret_report(report)
    tone_method = {
        "danger": st.error,
        "warning": st.warning,
        "success": st.success,
    }[interpretation["tone"]]
    tone_method(f"**{interpretation['level']}** · {interpretation['summary']}")
    _backend_summary(report)

    columns = st.columns(4)
    columns[0].metric("Analysierte Sätze", summary.get("sentences", 0))
    columns[1].metric("Faktische Aussagen", summary.get("factual_claims", 0))
    columns[2].metric("Fehlende Zitationen", summary.get("claims_missing_citations", 0))
    columns[3].metric("Literaturangaben", summary.get("references", 0))
    st.caption(
        "Diese vier Kennzahlen stammen aus Dokument- und Claim-Erkennung. Die gewählte "
        "Prüfmethode beeinflusst erst den Evidenzabgleich darunter."
    )

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("#### Empfohlene nächste Schritte")
        for action in interpretation["actions"]:
            st.markdown(f"- {action}")
    with right:
        st.markdown("#### Ergebnis der Quellenprüfung")
        counts = summary.get("verified_claim_status_counts", {})
        if counts:
            rows = [
                {"Bewertung": STATUS_LABELS.get(status, status), "Anzahl": count}
                for status, count in counts.items()
            ]
            st.dataframe(rows, hide_index=True, width="stretch")
        else:
            st.caption("Keine faktische Aussage konnte bis zur Quellenprüfung geführt werden.")

    st.info(interpretation["warning"], icon="ℹ️")
    with st.expander("So ist das Ergebnis entstanden"):
        module_1 = report.get("module_1", {}).get("summary", {})
        module_2 = report.get("module_2", {}).get("summary", {})
        module_3 = report.get("module_3", {}).get("summary", {})
        st.markdown(
            f"""
            1. **Dokument zerlegt:** {summary.get('sentences', 0)} Sätze und {summary.get('references', 0)} Literaturangaben erkannt.
            2. **Aussagen klassifiziert:** {module_1.get('factual_claims', summary.get('factual_claims', 0))} faktische Aussagen identifiziert.
            3. **Quellen geprüft:** Validierungsstatus `{module_2.get('status_counts', {})}`.
            4. **Evidenz abgeglichen:** {module_3.get('claims_verified', len(report.get('claim_verification', [])))} Aussagen mit dem gewählten Backend bewertet.
            5. **Prüfbedarf interpretiert:** Konflikte und offene Belege wurden priorisiert; es wurde keine neue Vorhersage erzeugt.
            """
        )


def _claims_view(report: dict[str, Any]) -> None:
    claims = report.get("claims") or report.get("module_1", {}).get("claims", [])
    verifications = {
        item.get("claim_index"): item for item in report.get("claim_verification", [])
    }
    if not claims:
        st.info("Keine Aussagen erkannt.")
        return

    filter_choice = st.selectbox(
        "Anzeigen",
        ["Alle Aussagen", "Nur Prüfbedarf", "Nur faktische Aussagen"],
        key="claim_filter",
    )
    visible = []
    for claim in claims:
        verification = verifications.get(claim.get("sentence_index"))
        has_review_need = claim.get("missing_citation") or (
            verification and verification.get("status") != "supported"
        )
        if filter_choice == "Nur Prüfbedarf" and not has_review_need:
            continue
        if filter_choice == "Nur faktische Aussagen" and claim.get("claim_type") != "factual_claim":
            continue
        visible.append((claim, verification))

    st.caption(f"{len(visible)} von {len(claims)} Aussagen")
    for claim, verification in visible:
        index = claim.get("sentence_index", "?")
        if claim.get("missing_citation"):
            icon, headline = "⚠️", "Zitation fehlt"
        elif verification:
            status = verification.get("status", "insufficient_evidence")
            icon = STATUS_ICONS.get(status, "⚪")
            headline = STATUS_LABELS.get(status, status)
        else:
            icon, headline = "🔹", CLAIM_TYPE_LABELS.get(claim.get("claim_type"), "Aussage")

        with st.expander(f"{icon} Satz {int(index) + 1 if isinstance(index, int) else index} · {headline}"):
            st.markdown(f"> {claim.get('sentence', '')}")
            meta_left, meta_right = st.columns(2)
            with meta_left:
                st.markdown(
                    f"**Typ:** {CLAIM_TYPE_LABELS.get(claim.get('claim_type'), claim.get('claim_type', '–'))}"
                )
                confidence = float(claim.get("classification_confidence", 0) or 0)
                st.markdown(
                    f"**Klassifikationssignal:** {confidence:.0%} · {confidence_label(confidence)}"
                )
            with meta_right:
                citations = claim.get("citations", [])
                markers = ", ".join(item.get("raw_text", "") for item in citations) or "keine"
                st.markdown(f"**Zitationen:** {markers}")
                st.markdown(f"**Abschnitt:** {claim.get('section', 'unbekannt')}")

            st.markdown(f"**Empfehlung:** {claim_recommendation(claim, verification)}")
            if verification:
                explanation = interpret_verification(verification)
                backend_error = (verification.get("metadata") or {}).get("backend_error")
                if backend_error:
                    st.error(f"Backend nicht verfügbar: {backend_error}")
                st.markdown(f"**Bedeutung:** {explanation['meaning']}")
                verify_confidence = float(verification.get("confidence", 0) or 0)
                st.caption(
                    f"Prüfsignal {verify_confidence:.0%} ({explanation['signal']}) · "
                    f"Backend: {verification.get('verifier', 'heuristic')}"
                )
                evidence = verification.get("evidence", [])
                if evidence:
                    st.markdown("**Gefundene Evidenz**")
                    for number, passage in enumerate(evidence[:3], start=1):
                        score = float(passage.get("score", 0) or 0)
                        st.markdown(
                            f"{number}. *Quelle {passage.get('source', 'unbekannt')} · "
                            f"Relevanz {score:.0%}*  \n{passage.get('text', '')}"
                        )
                with st.expander("Technische Begründung"):
                    st.write(verification.get("rationale", "Keine Begründung verfügbar."))
                    st.json(verification.get("metadata", {}))
            else:
                with st.expander("Technische Begründung"):
                    st.write(claim.get("classification_reason", "Keine Begründung verfügbar."))


def _comparison_view(
    report: dict[str, Any],
    path_or_name: str | None,
    content: bytes | None,
    display_name: str | None,
    enable_apis: bool,
) -> None:
    st.markdown("#### Automatischer Modellvergleich")
    st.write(
        "Alle ausgewählten Prüfer erhalten dasselbe Dokument. Claim-Erkennung und Evidenzbasis "
        "bleiben dadurch vergleichbar; dargestellt werden Urteile, Begründungen und Laufzeiten."
    )
    selected = st.multiselect(
        "Modelle auswählen",
        options=["heuristic", "ollama", "lora", "openai"],
        default=["heuristic", "ollama"],
        format_func=BACKEND_LABELS.get,
        key="comparison_backends",
    )
    if "lora" in selected:
        st.info("SciFact-LoRA wird lokal geladen und kann beim ersten Durchlauf etwas dauern.")
    openai_confirmed = True
    if "openai" in selected:
        estimated_calls = len(report.get("claim_verification", []))
        st.warning(
            f"OpenAI kann bis zu {estimated_calls} kostenpflichtige API-Aufrufe für dieses "
            "Dokument auslösen. Die genaue Zahl hängt von der verfügbaren Evidenz ab."
        )
        openai_confirmed = st.checkbox(
            "Ich bestätige, dass der OpenAI-Vergleich API-Kosten verursachen kann.",
            key="comparison_openai_confirmed",
        )

    can_compare = bool(path_or_name and display_name and len(selected) >= 2 and openai_confirmed)
    if len(selected) < 2:
        st.caption("Wähle mindestens zwei Modelle aus.")

    input_id = _analysis_signature(
        path_or_name,
        content,
        "heuristic",
        enable_apis,
        None,
    )[0]
    comparison_signature = (input_id, tuple(sorted(selected)), enable_apis)
    if st.button(
        "Ausgewählte Modelle automatisch vergleichen",
        type="primary",
        disabled=not can_compare,
        width="stretch",
        key="run_model_comparison",
    ):
        try:
            with st.status("Modellvergleich läuft …", expanded=True) as progress:
                reports = _run_comparison(
                    path_or_name=path_or_name or "",
                    content=content,
                    display_name=display_name or "Dokument",
                    backends=selected,
                    enable_apis=enable_apis,
                    existing_report=report,
                    existing_signature=st.session_state.get("claimguard_signature"),
                    progress=progress,
                )
                comparison = compare_reports(reports)
                st.session_state["claimguard_comparison"] = comparison
                st.session_state["claimguard_comparison_reports"] = reports
                st.session_state["claimguard_comparison_signature"] = comparison_signature
                progress.update(label="Modellvergleich abgeschlossen", state="complete")
        except Exception as exc:
            st.error(f"Der Modellvergleich konnte nicht abgeschlossen werden: {exc}")
            st.exception(exc)

    comparison = st.session_state.get("claimguard_comparison")
    if not comparison:
        st.caption("Nach dem Start erscheinen hier Gemeinsamkeiten und Unterschiede pro Aussage.")
        return
    if st.session_state.get("claimguard_comparison_signature") != comparison_signature:
        st.warning(
            "Dokument, API-Einstellung oder Modellauswahl wurde seit dem letzten Vergleich "
            "geändert. Starte den Vergleich erneut, um aktuelle Ergebnisse zu sehen."
        )

    summary = comparison["summary"]
    metrics = st.columns(5)
    metrics[0].metric("Modelle", summary["models"])
    metrics[1].metric("Verglichene Claims", summary["claims_compared"])
    metrics[2].metric("Übereinstimmungen", summary["agreements"])
    metrics[3].metric("Abweichungen", summary["disagreements"])
    metrics[4].metric("Backend-Fehler", summary["backend_errors"])
    st.info(comparison["warning"], icon="ℹ️")

    st.markdown("##### Übersicht je Backend")
    backend_rows = []
    for backend, values in comparison["backend_summary"].items():
        backend_rows.append(
            {
                "Backend": BACKEND_LABELS.get(backend, backend),
                "Modell": ", ".join(values["models"]) or "regelbasiert / nicht aufgerufen",
                "Modellaufrufe": values["model_calls"],
                "Laufzeit (ms)": values["latency_ms"],
                "Fehler": values["errors"],
                "Urteile": ", ".join(
                    f"{STATUS_LABELS.get(status, status)}: {count}"
                    for status, count in values["status_counts"].items()
                )
                or "keine",
            }
        )
    st.dataframe(backend_rows, hide_index=True, width="stretch")

    st.markdown("##### Vergleich pro Aussage")
    table_rows = []
    agreement_labels = {
        "agreement": "✅ gleich",
        "disagreement": "⚠️ unterschiedlich",
        "incomplete": "⚪ unvollständig",
    }
    for row in comparison["rows"]:
        display_row = {
            "Satz": int(row["claim_index"]) + 1,
            "Vergleich": agreement_labels[row["agreement"]],
            "Aussage": row["sentence"],
        }
        for backend in comparison["backends"]:
            result = row["models"][backend]
            if result["error"]:
                value = "Backend-Fehler"
            elif result["status"] is None:
                value = "–"
            else:
                confidence = float(result["confidence"] or 0)
                value = f"{STATUS_LABELS.get(result['status'], result['status'])} ({confidence:.0%})"
            display_row[BACKEND_LABELS.get(backend, backend)] = value
        table_rows.append(display_row)
    st.dataframe(table_rows, hide_index=True, width="stretch")

    disagreement_rows = [
        row for row in comparison["rows"] if row["agreement"] == "disagreement"
    ]
    detail_rows = disagreement_rows or comparison["rows"]
    if detail_rows:
        if disagreement_rows:
            st.markdown("##### Abweichungen im Detail")
        else:
            st.markdown("##### Ergebnisse im Detail")
        selected_index = st.selectbox(
            "Aussage auswählen",
            options=[row["claim_index"] for row in detail_rows],
            format_func=lambda index: (
                f"Satz {int(index) + 1}: "
                + next(row["sentence"] for row in detail_rows if row["claim_index"] == index)[:100]
            ),
            key="comparison_claim_detail",
        )
        selected_row = next(row for row in detail_rows if row["claim_index"] == selected_index)
        st.markdown(f"> {selected_row['sentence']}")
        columns = st.columns(len(comparison["backends"]))
        for column, backend in zip(columns, comparison["backends"]):
            result = selected_row["models"][backend]
            with column:
                with st.container(border=True):
                    st.markdown(f"**{BACKEND_LABELS.get(backend, backend)}**")
                    if result["error"]:
                        st.error("Backend-Fehler")
                        st.caption(result["error"])
                    elif result["status"] is None:
                        st.write("Kein Prüfergebnis")
                    else:
                        st.write(STATUS_LABELS.get(result["status"], result["status"]))
                        st.caption(
                            f"Signal: {float(result['confidence'] or 0):.0%} · "
                            f"Laufzeit: {result['latency_ms'] if result['latency_ms'] is not None else 'n/a'} ms"
                        )
                        if result["model"]:
                            st.caption(f"Modell: {result['model']}")
                        st.write(result["rationale"])

    st.download_button(
        "Vergleich als JSON herunterladen",
        json.dumps(comparison, indent=2, ensure_ascii=False),
        file_name="claimguard_model_comparison.json",
        mime="application/json",
        width="stretch",
        key="download_model_comparison",
    )


def _references_view(report: dict[str, Any]) -> None:
    references = report.get("references", [])
    validations = {
        item.get("reference_index"): item for item in report.get("reference_validation", [])
    }
    if not references:
        st.info("Kein Literaturverzeichnis erkannt.")
        return
    for reference in references:
        index = reference.get("index") or "?"
        validation = validations.get(reference.get("index"), {})
        title = reference.get("title") or reference.get("raw_text", "Unbekannte Quelle")[:80]
        with st.expander(f"[{index}] {title}"):
            left, right = st.columns(2)
            with left:
                st.markdown(f"**Autor:innen:** {', '.join(reference.get('authors') or []) or 'nicht erkannt'}")
                st.markdown(f"**Jahr:** {reference.get('year') or 'nicht erkannt'}")
                st.markdown(f"**DOI:** {reference.get('doi') or 'nicht erkannt'}")
            with right:
                st.markdown(f"**Validierung:** {validation.get('status', 'nicht geprüft')}")
                st.markdown(f"**Dienst:** {validation.get('source', 'lokal')}")
                st.markdown(f"**Details:** {validation.get('details', '–')}")
            st.caption(reference.get("raw_text", ""))


def _ai_view(report: dict[str, Any]) -> None:
    module = report.get("module_4", {})
    if not module.get("enabled"):
        st.info("Der optionale KI-Text-Indikator war für diese Analyse deaktiviert.")
        return
    results = module.get("results", [])
    st.warning(
        "KI-Text-Erkennung ist fehleranfällig. Diese Werte sind kein Nachweis der Autorschaft "
        "und dürfen nicht automatisch zu Sanktionen führen."
    )
    for item in results:
        with st.expander(
            f"Absatz {int(item.get('paragraph_index', 0)) + 1} · {item.get('label', 'unbekannt')}"
        ):
            st.write(item.get("text", ""))
            st.caption(
                f"Score: {float(item.get('score', 0) or 0):.3f} · "
                f"Konfidenz: {float(item.get('confidence', 0) or 0):.0%} · "
                f"Methode: {item.get('method', 'unbekannt')}"
            )
            st.write(item.get("rationale", ""))


def _downloads(report: dict[str, Any]) -> None:
    st.subheader("Bericht exportieren")
    payload = json.dumps(report, indent=2, ensure_ascii=False)
    st.download_button(
        "JSON-Bericht herunterladen",
        payload,
        file_name="claimguard_report.json",
        mime="application/json",
        width="stretch",
    )
    with st.expander("Rohdaten ansehen"):
        st.json(report)


def main() -> None:
    _configure_page()
    st.markdown(
        """
        <div class="cg-hero">
          <h1>🛡️ ClaimGuard</h1>
          <p>Akademische Aussagen, Zitationen und Quellenbelege nachvollziehbar prüfen.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    verifier, enable_apis, ai_method = _sidebar_settings()
    path_or_name, content, display_name = _input_area()
    can_analyze = bool(path_or_name and display_name)
    current_signature = _analysis_signature(
        path_or_name,
        content,
        verifier,
        enable_apis,
        ai_method,
    )
    if st.button(
        "Dokument analysieren",
        type="primary",
        disabled=not can_analyze,
        width="stretch",
    ):
        try:
            with st.spinner("Dokument wird analysiert und Evidenz wird zugeordnet …"):
                report = _run_analysis(
                    path_or_name=path_or_name or "",
                    content=content,
                    display_name=display_name or "Dokument",
                    verifier=verifier,
                    enable_apis=enable_apis,
                    ai_method=ai_method,
                )
                st.session_state["claimguard_report"] = report
                st.session_state["claimguard_signature"] = current_signature
        except Exception as exc:  # Streamlit must keep the session usable after backend errors.
            st.error(f"Die Analyse konnte nicht abgeschlossen werden: {exc}")
            st.exception(exc)

    report = st.session_state.get("claimguard_report")
    if not report:
        st.caption("Wähle ein Dokument aus und starte die Analyse. Das problematische Beispiel eignet sich für die erste Demo.")
        return

    if st.session_state.get("claimguard_signature") != current_signature:
        previous = report.get("configuration", {}).get("verifier", "unbekannt")
        st.warning(
            "Eingabe oder Einstellungen wurden geändert. Der unten angezeigte Bericht wurde "
            f"noch mit **{previous}** erstellt. Klicke erneut auf **Dokument analysieren**, "
            "um die neue Prüfmethode anzuwenden."
        )

    st.divider()
    used_verifier = report.get("configuration", {}).get("verifier", "heuristic")
    st.subheader(
        f"2 · Ergebnis für {report.get('input_path', 'Dokument')} · Methode: {used_verifier}"
    )
    tabs = st.tabs(
        ["Überblick", "Aussagen & Evidenz", "Modellvergleich", "Quellen", "KI-Text", "Export"]
    )
    with tabs[0]:
        _overview(report)
    with tabs[1]:
        _claims_view(report)
    with tabs[2]:
        _comparison_view(
            report=report,
            path_or_name=path_or_name,
            content=content,
            display_name=display_name,
            enable_apis=enable_apis,
        )
    with tabs[3]:
        _references_view(report)
    with tabs[4]:
        _ai_view(report)
    with tabs[5]:
        _downloads(report)


if __name__ == "__main__":
    main()
