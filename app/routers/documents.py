import asyncio
import base64
import io
import os
import time
from pathlib import Path

import fitz  # PyMuPDF
import httpx
from fastapi import APIRouter, UploadFile, File, HTTPException

from app.config import get_supabase, MAX_FILES, MAX_FILE_SIZE_MB, ALLOWED_EXTENSIONS
from app.models.schemas import (
    DocumentResponse,
    UploadResponse,
    ExtractRequest,
    ExtractResponse,
    DocumentStatus,
)
from app.services.ai_extractor import extract_from_images
from app.services.ai_tracker import track_ai_call, track_ai_error
from app.services.data_merger import merge_extractions

router = APIRouter()


def _validate_file(file: UploadFile):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"File type '{ext}' not allowed. Use: {ALLOWED_EXTENSIONS}")


def _pdf_to_pngs(pdf_bytes: bytes) -> list[bytes]:
    """Convert PDF bytes to list of PNG bytes (one per page)."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    pages = []
    for page in doc:
        # Render at 2x for better OCR quality
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        pages.append(pix.tobytes("png"))
    doc.close()
    return pages


@router.post("/upload", response_model=UploadResponse)
async def upload_documents(files: list[UploadFile] = File(...)):
    """Upload 1-6 documents. Validates, saves to Storage, converts PDF->PNG."""
    if len(files) > MAX_FILES:
        raise HTTPException(400, f"Maximum {MAX_FILES} files allowed")
    if len(files) == 0:
        raise HTTPException(400, "At least 1 file required")

    for f in files:
        _validate_file(f)

    sb = get_supabase()
    document_ids = []
    thumbnails = []

    for file in files:
        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(400, f"File '{file.filename}' exceeds {MAX_FILE_SIZE_MB}MB limit")

        # Create document record first to get the ID
        doc_record = sb.table("documents").insert({
            "filename": file.filename,
            "original_url": "",  # will update after upload
            "status": DocumentStatus.UPLOADED.value,
            "file_size_bytes": file_size,
        }).execute()

        doc_id = doc_record.data[0]["id"]
        ext = Path(file.filename).suffix.lower()

        # Upload original to storage
        original_path = f"originals/{doc_id}{ext}"
        sb.storage.from_("documents").upload(
            original_path,
            content,
            {"content-type": file.content_type or "application/octet-stream"},
        )
        original_url = sb.storage.from_("documents").get_public_url(original_path)

        # Convert to PNG pages
        image_urls = []
        if ext == ".pdf":
            png_pages = _pdf_to_pngs(content)
            page_count = len(png_pages)
            for i, png_bytes in enumerate(png_pages):
                img_path = f"images/{doc_id}_page_{i}.png"
                sb.storage.from_("documents").upload(
                    img_path,
                    png_bytes,
                    {"content-type": "image/png"},
                )
                img_url = sb.storage.from_("documents").get_public_url(img_path)
                image_urls.append(img_url)
        else:
            # Already an image
            img_path = f"images/{doc_id}{ext}"
            sb.storage.from_("documents").upload(
                img_path,
                content,
                {"content-type": file.content_type or "image/png"},
            )
            img_url = sb.storage.from_("documents").get_public_url(img_path)
            image_urls.append(img_url)
            page_count = 1

        # Update document with URLs
        sb.table("documents").update({
            "original_url": original_url,
            "image_urls": image_urls,
            "page_count": page_count,
        }).eq("id", doc_id).execute()

        document_ids.append(doc_id)
        thumbnails.append(image_urls[0] if image_urls else original_url)

    return UploadResponse(document_ids=document_ids, thumbnails=thumbnails)


@router.post("/extract", response_model=ExtractResponse)
async def extract_documents(request: ExtractRequest):
    """For each doc: AIExtractor + AITracker. DataMerger combines. Creates draft form."""
    if not request.document_ids:
        raise HTTPException(400, "At least 1 document_id required")

    sb = get_supabase()

    # Fetch all documents
    docs_result = sb.table("documents").select("*").in_("id", request.document_ids).execute()
    docs = docs_result.data

    if len(docs) != len(request.document_ids):
        raise HTTPException(404, "One or more documents not found")

    # Mark all as processing
    for doc in docs:
        sb.table("documents").update({"status": DocumentStatus.PROCESSING.value}).eq("id", doc["id"]).execute()

    # Extract each document in parallel using asyncio.gather
    async def process_one(doc: dict):
        doc_id = doc["id"]
        image_urls = doc.get("image_urls", [])

        if not image_urls:
            raise HTTPException(400, f"Document {doc_id} has no images")

        # Download images and convert to base64
        images_b64 = []
        async with httpx.AsyncClient() as http:
            for url in image_urls:
                resp = await http.get(url)
                resp.raise_for_status()
                b64 = base64.b64encode(resp.content).decode("utf-8")
                images_b64.append(b64)

        # Call AI extractor
        start_ms = time.time()
        try:
            extraction, raw_dict, ai_response = await extract_from_images(images_b64)
            duration_ms = int((time.time() - start_ms) * 1000)

            # Track usage
            usage_log = await track_ai_call(
                document_id=doc_id,
                doc_type=extraction.doc_type,
                page_number=doc.get("page_count", 1),
                ai_response=ai_response,
            )
            # Update duration
            sb.table("ai_usage_logs").update({"duration_ms": duration_ms}).eq("document_id", doc_id).execute()

            # Save extraction to DB
            sb.table("extractions").insert({
                "document_id": doc_id,
                "raw_ai_response": raw_dict,
                "extracted_fields": extraction.model_dump(),
                "doc_type_detected": extraction.doc_type,
                "processing_time_ms": duration_ms,
            }).execute()

            # Update document status and doc_type
            sb.table("documents").update({
                "status": DocumentStatus.EXTRACTED.value,
                "doc_type": extraction.doc_type,
            }).eq("id", doc_id).execute()

            return extraction, extraction.doc_type or "unknown"

        except Exception as e:
            duration_ms = int((time.time() - start_ms) * 1000)
            await track_ai_error(doc_id, None, None, str(e), duration_ms)
            sb.table("documents").update({"status": DocumentStatus.ERROR.value}).eq("id", doc_id).execute()
            raise HTTPException(500, f"Extraction failed for document {doc_id}: {str(e)}")

    # Run all extractions in parallel
    results = await asyncio.gather(*[process_one(doc) for doc in docs])

    # Merge all extractions
    merged_data, confidence_summary = merge_extractions(list(results))

    # Create draft form
    form_record = sb.table("forms").insert({
        "form_data": merged_data,
        "original_form_data": merged_data,
        "status": "draft",
        "confidence_summary": confidence_summary.model_dump(),
    }).execute()

    form_id = form_record.data[0]["id"]

    # Create form_documents junction records
    for doc_id in request.document_ids:
        sb.table("form_documents").insert({
            "form_id": form_id,
            "document_id": doc_id,
        }).execute()

    return ExtractResponse(
        form_id=form_id,
        merged_data=merged_data,
        confidence=confidence_summary,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Return document + metadata."""
    sb = get_supabase()
    result = sb.table("documents").select("*").eq("id", document_id).execute()

    if not result.data:
        raise HTTPException(404, "Document not found")

    doc = result.data[0]
    return DocumentResponse(
        id=doc["id"],
        filename=doc["filename"],
        original_url=doc["original_url"],
        image_urls=doc.get("image_urls", []),
        doc_type=doc.get("doc_type"),
        status=doc["status"],
        page_count=doc.get("page_count", 1),
        file_size_bytes=doc.get("file_size_bytes"),
        created_at=doc.get("created_at"),
    )
