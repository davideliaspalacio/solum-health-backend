from fastapi import APIRouter

from app.config import get_supabase
from app.models.schemas import AccuracyResponse, AIUsageResponse

router = APIRouter()


@router.get("/accuracy", response_model=AccuracyResponse)
async def get_accuracy():
    """Global accuracy, by field section, by doc type, by confidence."""
    sb = get_supabase()

    # Get all forms and corrections
    forms_result = sb.table("forms").select("id, status, confidence_summary").execute()
    corrections_result = sb.table("corrections").select("*").execute()

    forms = forms_result.data
    corrections = corrections_result.data
    total_forms = len(forms)
    total_corrections = len(corrections)

    # Global accuracy: forms with 0 corrections / total approved forms
    approved_forms = [f for f in forms if f["status"] == "approved"]
    if approved_forms:
        forms_with_corrections = set(c["form_id"] for c in corrections)
        perfect_forms = [f for f in approved_forms if f["id"] not in forms_with_corrections]
        global_accuracy = len(perfect_forms) / len(approved_forms) if approved_forms else 0.0
    else:
        global_accuracy = 0.0

    # By field section
    by_section = {}
    for c in corrections:
        section = c.get("field_section") or "unknown"
        by_section[section] = by_section.get(section, 0) + 1

    # By doc type — get from form_documents + documents
    by_doc_type = {}
    form_docs = sb.table("form_documents").select("form_id, document_id").execute().data
    doc_ids = list(set(fd["document_id"] for fd in form_docs))
    if doc_ids:
        docs = sb.table("documents").select("id, doc_type").in_("id", doc_ids).execute().data
        doc_type_map = {d["id"]: d.get("doc_type", "unknown") for d in docs}
        form_to_types = {}
        for fd in form_docs:
            fid = fd["form_id"]
            dtype = doc_type_map.get(fd["document_id"], "unknown")
            form_to_types.setdefault(fid, set()).add(dtype)

        for c in corrections:
            types = form_to_types.get(c["form_id"], {"unknown"})
            for t in types:
                by_doc_type[t] = by_doc_type.get(t, 0) + 1

    # By confidence level
    by_confidence = {}
    for c in corrections:
        conf = c.get("original_confidence") or "unknown"
        by_confidence[conf] = by_confidence.get(conf, 0) + 1

    return AccuracyResponse(
        global_accuracy=round(global_accuracy, 4),
        by_field_section=by_section,
        by_doc_type=by_doc_type,
        by_confidence=by_confidence,
        total_forms=total_forms,
        total_corrections=total_corrections,
    )


@router.get("/ai-usage", response_model=AIUsageResponse)
async def get_ai_usage():
    """Total cost, tokens, avg per doc, duration, by model, recent calls."""
    sb = get_supabase()

    logs_result = sb.table("ai_usage_logs").select("*").order("created_at", desc=True).execute()
    logs = logs_result.data

    if not logs:
        return AIUsageResponse(
            total_cost_usd=0.0,
            total_tokens=0,
            avg_tokens_per_doc=0.0,
            avg_duration_ms=0.0,
            by_doc_type={},
            by_model={},
            recent_calls=[],
        )

    total_cost = sum(float(l.get("estimated_cost") or 0) for l in logs)
    total_tokens = sum(l.get("total_tokens") or 0 for l in logs)
    total_duration = sum(l.get("duration_ms") or 0 for l in logs)
    count = len(logs)

    # By doc type
    by_doc_type = {}
    for l in logs:
        dt = l.get("doc_type") or "unknown"
        entry = by_doc_type.setdefault(dt, {"count": 0, "tokens": 0, "cost": 0.0})
        entry["count"] += 1
        entry["tokens"] += l.get("total_tokens") or 0
        entry["cost"] += float(l.get("estimated_cost") or 0)

    # By model
    by_model = {}
    for l in logs:
        model = l.get("model") or "unknown"
        entry = by_model.setdefault(model, {"count": 0, "tokens": 0, "cost": 0.0})
        entry["count"] += 1
        entry["tokens"] += l.get("total_tokens") or 0
        entry["cost"] += float(l.get("estimated_cost") or 0)

    # Recent calls (last 20)
    recent = []
    for l in logs[:20]:
        recent.append({
            "id": l["id"],
            "document_id": l.get("document_id"),
            "doc_type": l.get("doc_type"),
            "model": l.get("model"),
            "total_tokens": l.get("total_tokens"),
            "estimated_cost": float(l.get("estimated_cost") or 0),
            "duration_ms": l.get("duration_ms"),
            "status": l.get("status"),
            "created_at": l.get("created_at"),
        })

    return AIUsageResponse(
        total_cost_usd=round(total_cost, 6),
        total_tokens=total_tokens,
        avg_tokens_per_doc=round(total_tokens / count, 1) if count else 0.0,
        avg_duration_ms=round(total_duration / count, 1) if count else 0.0,
        by_doc_type=by_doc_type,
        by_model=by_model,
        recent_calls=recent,
    )
