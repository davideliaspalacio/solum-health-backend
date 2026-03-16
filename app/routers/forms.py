from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.config import get_supabase
from app.services.pdf_filler import fill_pdf
from app.models.schemas import (
    FormResponse,
    FormUpdateRequest,
    FormUpdateResponse,
    FormApproveResponse,
    FormStatus,
    DocumentResponse,
    ConfidenceSummary,
)

router = APIRouter()


def _build_form_response(form: dict, source_docs: list[dict] | None = None) -> FormResponse:
    """Build a FormResponse from a DB row."""
    docs = []
    if source_docs:
        for d in source_docs:
            docs.append(DocumentResponse(
                id=d["id"],
                filename=d["filename"],
                original_url=d["original_url"],
                image_urls=d.get("image_urls", []),
                doc_type=d.get("doc_type"),
                status=d["status"],
                page_count=d.get("page_count", 1),
                file_size_bytes=d.get("file_size_bytes"),
                created_at=d.get("created_at"),
            ))

    conf = form.get("confidence_summary")
    confidence = ConfidenceSummary(**conf) if conf else None

    return FormResponse(
        id=form["id"],
        form_type=form.get("form_type", "service_request"),
        form_data=form.get("form_data", {}),
        original_form_data=form.get("original_form_data"),
        status=form["status"],
        confidence_summary=confidence,
        source_documents=docs,
        created_at=form.get("created_at"),
        updated_at=form.get("updated_at"),
        approved_at=form.get("approved_at"),
    )


@router.get("/{form_id}", response_model=FormResponse)
async def get_form(form_id: str):
    """Return form + confidence per field + source documents."""
    sb = get_supabase()

    # Get form
    form_result = sb.table("forms").select("*").eq("id", form_id).execute()
    if not form_result.data:
        raise HTTPException(404, "Form not found")
    form = form_result.data[0]

    # Get source documents via junction table
    junction = sb.table("form_documents").select("document_id").eq("form_id", form_id).execute()
    doc_ids = [r["document_id"] for r in junction.data]

    source_docs = []
    if doc_ids:
        docs_result = sb.table("documents").select("*").in_("id", doc_ids).execute()
        source_docs = docs_result.data

    return _build_form_response(form, source_docs)


@router.put("/{form_id}", response_model=FormUpdateResponse)
async def update_form(form_id: str, request: FormUpdateRequest):
    """Compare new vs original field by field. Auto-create corrections."""
    sb = get_supabase()

    # Get current form
    form_result = sb.table("forms").select("*").eq("id", form_id).execute()
    if not form_result.data:
        raise HTTPException(404, "Form not found")
    form = form_result.data[0]

    if form["status"] == FormStatus.APPROVED.value:
        raise HTTPException(400, "Cannot update an approved form")

    original_data = form.get("original_form_data", {})
    new_data = request.form_data

    # Compare field by field and create corrections
    corrections = []
    for key, new_field in new_data.items():
        original_field = original_data.get(key, {})

        # Extract values to compare
        new_value = new_field.get("value") if isinstance(new_field, dict) else new_field
        original_value = original_field.get("value") if isinstance(original_field, dict) else original_field

        if str(new_value) != str(original_value) and new_value is not None:
            # Parse section.field_name
            parts = key.split(".", 1)
            field_section = parts[0] if len(parts) > 1 else None
            field_name = parts[1] if len(parts) > 1 else key

            original_confidence = None
            if isinstance(original_field, dict):
                original_confidence = original_field.get("confidence")

            corrections.append({
                "form_id": form_id,
                "field_name": field_name,
                "field_section": field_section,
                "original_value": str(original_value) if original_value else None,
                "corrected_value": str(new_value),
                "original_confidence": original_confidence,
            })

    # Insert corrections
    if corrections:
        sb.table("corrections").insert(corrections).execute()

    # Update form data
    now = datetime.now(timezone.utc).isoformat()
    sb.table("forms").update({
        "form_data": new_data,
        "status": FormStatus.IN_REVIEW.value,
        "updated_at": now,
    }).eq("id", form_id).execute()

    # Fetch updated form
    updated = sb.table("forms").select("*").eq("id", form_id).execute()

    return FormUpdateResponse(
        corrections_count=len(corrections),
        form=_build_form_response(updated.data[0]),
    )


@router.get("/{form_id}/pdf")
async def download_form_pdf(form_id: str):
    """Generate a filled PDF from form data and return as download."""
    sb = get_supabase()

    form_result = sb.table("forms").select("*").eq("id", form_id).execute()
    if not form_result.data:
        raise HTTPException(404, "Form not found")

    form_data = form_result.data[0].get("form_data", {})
    pdf_bytes = fill_pdf(form_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="service-request-{form_id[:8]}.pdf"'},
    )


@router.put("/{form_id}/approve", response_model=FormApproveResponse)
async def approve_form(form_id: str):
    """Set status='approved'."""
    sb = get_supabase()

    form_result = sb.table("forms").select("*").eq("id", form_id).execute()
    if not form_result.data:
        raise HTTPException(404, "Form not found")

    now = datetime.now(timezone.utc)
    sb.table("forms").update({
        "status": FormStatus.APPROVED.value,
        "approved_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }).eq("id", form_id).execute()

    return FormApproveResponse(
        status=FormStatus.APPROVED,
        approved_at=now,
    )
