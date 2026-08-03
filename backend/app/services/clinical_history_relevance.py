"""Filter patient clinical history to biologically relevant items for the current visit."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.azure_openai_client import azure_openai_json_chat

_RELEVANCE_SYSTEM = """
You filter a patient's clinical history for biological relevance to the current visit.

Return ONLY valid JSON with this shape:
{
  "included": [
    {
      "category": "condition|surgery|allergy|prior_report|legacy_document",
      "label": "short human-readable label",
      "relevance_reason": "why this matters for the current presentation"
    }
  ],
  "excluded": [
    {
      "category": "condition|surgery|allergy|prior_report|legacy_document",
      "label": "short human-readable label",
      "relevance_reason": "why this is not relevant now"
    }
  ]
}

Rules:
- INCLUDE same organ system, known comorbidities affecting treatment (e.g. diabetes + infection),
  prior related diagnosis, prior related surgery affecting current site, relevant prior abnormal labs.
- EXCLUDE unrelated orthopaedic history for unrelated chief complaint (knee surgery + headache),
  unrelated prior oncology workup for acute URI unless metastatic/workup overlap.
- Profile allergies are always included when plausibly relevant to prescribed medicines.
- When uncertain about a comorbidity like diabetes, include it with a brief reason.
- Every history item supplied must appear exactly once in included or excluded.
""".strip()

_request_cache: dict[str, dict[str, Any]] = {}


def _history_hash(history: dict[str, Any] | None) -> str:
    payload = json.dumps(history or {}, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _diagnosis_hash(
    diagnosis: str,
    symptoms: list[Any] | None,
    test_results: list[dict[str, Any]] | None,
) -> str:
    payload = json.dumps(
        {
            "diagnosis": diagnosis,
            "symptoms": symptoms or [],
            "test_results": test_results or [],
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _flatten_history_items(history: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    profile = history.get("profile") or {}

    for index, condition in enumerate(profile.get("conditions") or []):
        if not isinstance(condition, dict):
            continue
        name = str(condition.get("name") or "").strip()
        if name:
            items.append(
                {
                    "id": f"profile_condition:{index}",
                    "category": "condition",
                    "label": name,
                    "data": condition,
                }
            )

    for index, surgery in enumerate(profile.get("surgeries") or []):
        if not isinstance(surgery, dict):
            continue
        name = str(surgery.get("name") or "").strip()
        if name:
            items.append(
                {
                    "id": f"profile_surgery:{index}",
                    "category": "surgery",
                    "label": name,
                    "data": surgery,
                }
            )

    for index, allergy in enumerate(profile.get("allergies") or []):
        if not isinstance(allergy, dict):
            continue
        name = str(allergy.get("name") or "").strip()
        if name:
            items.append(
                {
                    "id": f"profile_allergy:{index}",
                    "category": "allergy",
                    "label": name,
                    "data": allergy,
                }
            )

    for index, report in enumerate(history.get("prior_reports") or []):
        if not isinstance(report, dict):
            continue
        diagnosis = str(report.get("diagnosis") or "").strip()
        label = diagnosis or f"Prior report {index + 1}"
        items.append(
            {
                "id": f"prior_report:{index}",
                "category": "prior_report",
                "label": label,
                "data": report,
            }
        )

    for index, document in enumerate(history.get("legacy_documents") or []):
        if not isinstance(document, dict):
            continue
        summary = document.get("extractedSummary") or {}
        diagnosis = str(summary.get("diagnosis") or "").strip()
        doc_type = str(document.get("documentType") or "document")
        doc_date = str(document.get("documentDate") or "")
        label = diagnosis or f"{doc_type} ({doc_date or 'undated'})"
        items.append(
            {
                "id": f"legacy_document:{index}",
                "category": "legacy_document",
                "label": label,
                "data": document,
            }
        )

    return items


def _filter_profile_items(
    profile: dict[str, Any],
    included_ids: set[str],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    result = {"conditions": [], "surgeries": [], "allergies": []}
    for item in items:
        if item["id"] not in included_ids:
            continue
        data = item.get("data") or {}
        if item["category"] == "condition":
            result["conditions"].append(data)
        elif item["category"] == "surgery":
            result["surgeries"].append(data)
        elif item["category"] == "allergy":
            result["allergies"].append(data)
    return result


def _filter_list_items(
    source_key: str,
    history: dict[str, Any],
    included_ids: set[str],
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in items:
        if item["id"] not in included_ids:
            continue
        if item["category"] in {"prior_report", "legacy_document"}:
            filtered.append(item["data"])
    for index, entry in enumerate(history.get(source_key) or []):
        item_id = (
            f"prior_report:{index}"
            if source_key == "prior_reports"
            else f"legacy_document:{index}"
        )
        if item_id in included_ids and entry not in filtered:
            filtered.append(entry)
    return filtered


def _heuristic_filter(
    diagnosis: str,
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    diagnosis_lower = diagnosis.lower()
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    ortho_markers = ("knee", "arthroscopy", "orthopaedic", "orthopedic", "hip", "acl")
    headache_markers = ("headache", "migraine", "cephalgia")
    metabolic_markers = ("diabetes", "diabetic", "hypertension", "renal", "kidney")
    infection_markers = ("infection", "bacterial", "sepsis", "pneumonia", "uti")
    fever_markers = ("fever", "pyrexia", "malaria", "dengue", "typhoid")

    current_headache = any(marker in diagnosis_lower for marker in headache_markers)
    current_infection = any(marker in diagnosis_lower for marker in infection_markers)
    current_fever = any(marker in diagnosis_lower for marker in fever_markers)

    for item in items:
        label_lower = str(item.get("label") or "").lower()
        category = item.get("category")

        if category == "allergy":
            included.append(
                {
                    "category": category,
                    "label": item["label"],
                    "relevance_reason": "Allergy history may affect medicine choices.",
                }
            )
            continue

        if current_headache and any(marker in label_lower for marker in ortho_markers):
            excluded.append(
                {
                    "category": category,
                    "label": item["label"],
                    "relevance_reason": "Orthopaedic history is not connected to headache.",
                }
            )
            continue

        if current_infection and any(marker in label_lower for marker in metabolic_markers):
            included.append(
                {
                    "category": category,
                    "label": item["label"],
                    "relevance_reason": "Comorbidity may affect infection treatment.",
                }
            )
            continue

        if current_fever and "malaria" in label_lower:
            included.append(
                {
                    "category": category,
                    "label": item["label"],
                    "relevance_reason": "Prior malaria is relevant to fever evaluation.",
                }
            )
            continue

        if category in {"prior_report", "legacy_document"} and any(
            marker in label_lower for marker in fever_markers
        ):
            if current_fever:
                included.append(
                    {
                        "category": category,
                        "label": item["label"],
                        "relevance_reason": "Prior related illness informs current fever workup.",
                    }
                )
                continue

        included.append(
            {
                "category": category,
                "label": item["label"],
                "relevance_reason": "Potentially relevant to current clinical context.",
            }
        )

    return {"included": included, "excluded": excluded}


def history_context_labels(clinical_history: dict[str, Any] | None) -> list[str]:
    return history_context_snippets(clinical_history or {})


def filter_relevant_clinical_history(
    current_diagnosis: str,
    current_symptoms: list[Any] | None,
    current_tests: list[dict[str, Any]] | None,
    history: dict[str, Any] | None,
    _cache: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    history = history or {}
    flat_items = _flatten_history_items(history)
    if not flat_items:
        return {
            "profile": history.get("profile") or {"conditions": [], "surgeries": [], "allergies": []},
            "prior_reports": [],
            "legacy_documents": [],
            "included": [],
            "excluded": [],
            "included_count": 0,
            "excluded_count": 0,
        }

    cache_key = (
        f"{_diagnosis_hash(current_diagnosis, current_symptoms, current_tests)}:"
        f"{_history_hash(history)}"
    )
    cache_store = _cache if _cache is not None else _request_cache
    if cache_key in cache_store:
        return cache_store[cache_key]

    user = f"""
Current diagnosis: {current_diagnosis}
Current symptoms: {json.dumps(current_symptoms or [], ensure_ascii=False)}
Current test results: {json.dumps(current_tests or [], ensure_ascii=False)}

Patient history items:
{json.dumps(
    [{"id": item["id"], "category": item["category"], "label": item["label"]} for item in flat_items],
    ensure_ascii=False,
)}
""".strip()

    parsed: dict[str, Any] = {}
    try:
        parsed = azure_openai_json_chat(_RELEVANCE_SYSTEM, user, max_tokens=1800)
    except Exception:
        parsed = {}

    included_meta: list[dict[str, Any]] = []
    excluded_meta: list[dict[str, Any]] = []
    included_ids: set[str] = set()
    excluded_ids: set[str] = set()
    used_item_classifier = False

    classified_items = parsed.get("items")
    if isinstance(classified_items, list) and classified_items:
        used_item_classifier = True
        flat_by_id = {item["id"]: item for item in flat_items}
        for entry in classified_items:
            if not isinstance(entry, dict):
                continue
            item_id = str(entry.get("id") or "").strip()
            flat = flat_by_id.get(item_id)
            if not flat:
                continue
            meta = {
                "category": flat["category"],
                "label": flat["label"],
                "relevance_reason": str(entry.get("relevance_reason") or "").strip(),
            }
            if entry.get("relevant") is False:
                excluded_meta.append(meta)
                excluded_ids.add(item_id)
            else:
                included_meta.append(meta)
                included_ids.add(item_id)
    else:
        included_meta = (
            parsed.get("included") if isinstance(parsed.get("included"), list) else []
        )
        excluded_meta = (
            parsed.get("excluded") if isinstance(parsed.get("excluded"), list) else []
        )

    if not included_meta and not excluded_meta:
        heuristic = _heuristic_filter(current_diagnosis, flat_items)
        included_meta = heuristic["included"]
        excluded_meta = heuristic["excluded"]

    if not used_item_classifier:
        label_to_id = {item["label"].lower(): item["id"] for item in flat_items}

        for entry in included_meta:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "").strip()
            item_id = label_to_id.get(label.lower())
            if item_id:
                included_ids.add(item_id)

        for entry in excluded_meta:
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("label") or "").strip()
            item_id = label_to_id.get(label.lower())
            if item_id:
                excluded_ids.add(item_id)

        for item in flat_items:
            if item["id"] not in included_ids and item["id"] not in excluded_ids:
                included_ids.add(item["id"])

        for item_id in list(included_ids):
            if item_id in excluded_ids:
                included_ids.discard(item_id)

    filtered_profile = _filter_profile_items(
        history.get("profile") or {},
        included_ids,
        flat_items,
    )
    filtered_prior_reports = _filter_list_items(
        "prior_reports",
        history,
        included_ids,
        flat_items,
    )
    filtered_legacy_documents = _filter_list_items(
        "legacy_documents",
        history,
        included_ids,
        flat_items,
    )

    included = [
        {
            "category": entry.get("category"),
            "label": entry.get("label"),
            "relevance_reason": entry.get("relevance_reason")
            or "Relevant to the current clinical presentation.",
        }
        for entry in included_meta
        if isinstance(entry, dict) and entry.get("label")
    ]
    excluded = [
        {
            "category": entry.get("category"),
            "label": entry.get("label"),
            "relevance_reason": entry.get("relevance_reason")
            or "Not connected to the current presentation.",
        }
        for entry in excluded_meta
        if isinstance(entry, dict) and entry.get("label")
    ]

    if not included and included_ids:
        included = [
            {
                "category": item["category"],
                "label": item["label"],
                "relevance_reason": "Included for clinical context.",
            }
            for item in flat_items
            if item["id"] in included_ids
        ]

    result = {
        "profile": filtered_profile,
        "prior_reports": filtered_prior_reports,
        "legacy_documents": filtered_legacy_documents,
        "included": included,
        "excluded": excluded,
        "included_count": len(included),
        "excluded_count": len(excluded),
    }
    cache_store[cache_key] = result
    return result


def clear_relevance_cache() -> None:
    _request_cache.clear()


def history_context_snippets(filtered_history: dict[str, Any]) -> list[str]:
    snippets: list[str] = []
    profile = filtered_history.get("profile") or {}
    for condition in profile.get("conditions") or []:
        name = str(condition.get("name") or "").strip()
        if name:
            snippets.append(f"Condition: {name}")
    for surgery in profile.get("surgeries") or []:
        name = str(surgery.get("name") or "").strip()
        if name:
            snippets.append(f"Surgery: {name}")
    for report in filtered_history.get("prior_reports") or []:
        diagnosis = str(report.get("diagnosis") or "").strip()
        if diagnosis:
            snippets.append(f"Prior diagnosis: {diagnosis}")
    for document in filtered_history.get("legacy_documents") or []:
        summary = document.get("extractedSummary") or {}
        diagnosis = str(summary.get("diagnosis") or "").strip()
        if diagnosis:
            snippets.append(f"Legacy document diagnosis: {diagnosis}")
    return snippets
