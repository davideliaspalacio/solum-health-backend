import json
import base64
from openai import AsyncOpenAI
from app.config import OPENAI_API_KEY, GPT_MODEL
from app.models.schemas import ExtractionResult

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """You are a medical document data extractor. Your goal is to extract data from medical documents (clinical notes, insurance cards, referrals, etc.) to auto-fill a "Request for Approval of Services" form with sections A through G.

Analyze the provided document image(s) and extract ALL available fields into structured JSON.

Each field uses this format: {"value": "...", "confidence": "high|medium|low|missing", "needs_review": false, "reason": null}

Return ONLY valid JSON with this exact structure:
{
  "doc_type": "insurance_card|intake_form|referral_letter|clinical_note|lab_results|handwritten_note",
  "header": {
    "payer": <field>,
    "date_of_request": <field>,
    "payer_fax": <field>,
    "payer_phone": <field>
  },
  "section_a": {
    "member_name": <field>,
    "date_of_birth": <field>,
    "gender": <field>,
    "member_id": <field>,
    "group_number": <field>,
    "phone_number": <field>,
    "address": <field>
  },
  "section_b": {
    "provider_name": <field>,
    "provider_npi": <field>,
    "facility_practice_name": <field>,
    "tax_id": <field>,
    "phone": <field>,
    "fax": <field>,
    "address": <field>
  },
  "section_c": {
    "referring_provider_name": <field>,
    "referring_provider_npi": <field>,
    "phone": <field>
  },
  "section_d": {
    "type_of_service": <field>,
    "service_setting": <field>,
    "cpt_hcpcs_codes": <field>,
    "icd10_diagnosis_codes": <field>,
    "diagnosis_descriptions": <field>,
    "requested_start_date": <field>,
    "requested_end_date": <field>,
    "number_of_sessions": <field>,
    "frequency": <field>
  },
  "section_e": {
    "presenting_symptoms": <field>,
    "relevant_clinical_history": <field>,
    "medications": [
      {
        "medication": {"value": "Lisinopril", "confidence": "high", "needs_review": false, "reason": null},
        "dose": {"value": "20mg", "confidence": "high", "needs_review": false, "reason": null},
        "frequency": {"value": "daily", "confidence": "high", "needs_review": false, "reason": null},
        "prescriber": {"value": "Dr. Smith", "confidence": "medium", "needs_review": true, "reason": "inferred from context"}
      }
    ],
    "assessment_tools": [
      {
        "tool": {"value": "PHQ-9", "confidence": "high", "needs_review": false, "reason": null},
        "score": {"value": "15", "confidence": "high", "needs_review": false, "reason": null},
        "date": {"value": "2026-01-10", "confidence": "medium", "needs_review": true, "reason": "partially visible"}
      }
    ],
    "treatment_goals": <field>
  },
  "section_f": {
    "medical_necessity": <field>,
    "risk_if_not_provided": <field>
  },
  "section_g": {
    "provider_signature": <field>,
    "printed_name": <field>,
    "date": <field>,
    "license_number": <field>
  }
}

Rules:
- Set "confidence" to "high" if clearly readable, "medium" if partially visible or inferred, "low" if guessed, "missing" if not found.
- Set "needs_review" to true for medium, low, or missing confidence.
- For "member_name", format as "Last, First, MI" if all parts are available.
- For "type_of_service", use one of: Outpatient, Inpatient, Intensive Outpatient, Partial Hospitalization, Residential, Other.
- For "icd10_diagnosis_codes" and "cpt_hcpcs_codes", join multiple values with commas.
- IMPORTANT: "medications" and "assessment_tools" are arrays of objects. Every sub-field inside each object MUST use the full field format {"value": "...", "confidence": "...", "needs_review": ..., "reason": ...}. Do NOT use plain strings or nulls — always wrap in the field object.
- If no medications or assessments are found, return empty arrays [].
- "medical_necessity" should answer: "Why is this level of care medically necessary?"
- "risk_if_not_provided" should answer: "What is the risk if services are not provided?"
- Set "reason" when needs_review is true (e.g., "partially obscured", "handwritten - hard to read", "not found in document").
- If a field is not present in the document, set value to null and confidence to "missing".
"""


async def extract_from_images(
    images_base64: list[str],
    doc_type_hint: str | None = None,
) -> tuple[ExtractionResult, dict]:
    """
    Send document images to GPT-4o-mini for extraction.
    Returns (ExtractionResult, raw_response_dict).
    """
    # Build message content with images
    content = [{"type": "text", "text": "Extract all medical/insurance fields from this document."}]

    for img_b64 in images_base64:
        # Detect if it's already a data URI or raw base64
        if img_b64.startswith("data:"):
            image_url = img_b64
        else:
            image_url = f"data:image/png;base64,{img_b64}"

        content.append({
            "type": "image_url",
            "image_url": {"url": image_url, "detail": "high"},
        })

    if doc_type_hint:
        content[0]["text"] += f"\nDocument type hint: {doc_type_hint}"

    response = await client.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_format={"type": "json_object"},
        max_tokens=4096,
        temperature=0.1,
    )

    raw_text = response.choices[0].message.content
    raw_dict = json.loads(raw_text)

    # Parse into our Pydantic model
    result = ExtractionResult.model_validate(raw_dict)

    return result, raw_dict, response
