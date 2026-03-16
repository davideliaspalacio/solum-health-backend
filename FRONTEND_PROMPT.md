# Prompt: Build Frontend for Solum Health

## What is Solum Health?

Solum Health is a medical document processing system. Users upload medical documents (clinical notes, insurance cards, referrals, lab results, etc.), an AI (GPT-4o-mini) extracts structured data from them, and the system auto-fills a specific form: **"Request for Approval of Services"** — a 2-page form with 7 sections (A through G). Users then review, correct, and approve the form.

## Tech Stack

- **Frontend**: React + TypeScript + Vite + Tailwind CSS + shadcn/ui
- **Backend**: FastAPI (Python) — already built, running at `http://localhost:8000`
- **Database/Storage**: Supabase (Postgres + Storage) — the frontend does NOT talk to Supabase directly, everything goes through the API

Create the frontend project inside: `/Users/1234/ownProyecto/healthcare-test/frontend/`

## Backend API Reference

Base URL: `http://localhost:8000`

### Endpoints

#### 1. `POST /api/documents/upload`
Upload 1-6 medical documents (PDF, PNG, JPG). Multipart form data with field name `files`.

**Response** (`UploadResponse`):
```json
{
  "document_ids": ["uuid1", "uuid2"],
  "thumbnails": ["https://storage-url/image1.png", "https://storage-url/image2.png"]
}
```

#### 2. `POST /api/documents/extract`
Sends documents to AI for extraction, merges results, creates a draft form.

**Request**:
```json
{ "document_ids": ["uuid1", "uuid2"] }
```

**Response** (`ExtractResponse`):
```json
{
  "form_id": "uuid",
  "merged_data": { ... },  // flattened fields (see Field Structure below)
  "confidence": { "high": 12, "medium": 5, "low": 2, "missing": 8 }
}
```

#### 3. `GET /api/forms/{form_id}`
Returns the full form with confidence per field and source documents.

**Response** (`FormResponse`):
```json
{
  "id": "uuid",
  "form_type": "service_request",
  "form_data": { ... },           // current field values (see Field Structure below)
  "original_form_data": { ... },  // original AI extraction (for diff comparison)
  "status": "draft|in_review|approved",
  "confidence_summary": { "high": 12, "medium": 5, "low": 2, "missing": 8 },
  "source_documents": [
    {
      "id": "uuid",
      "filename": "insurance_card.pdf",
      "original_url": "https://...",
      "image_urls": ["https://page1.png", "https://page2.png"],
      "doc_type": "insurance_card",
      "status": "extracted",
      "page_count": 2,
      "file_size_bytes": 123456,
      "created_at": "2026-03-16T..."
    }
  ],
  "created_at": "...",
  "updated_at": "...",
  "approved_at": null
}
```

#### 4. `PUT /api/forms/{form_id}`
Update form fields (user corrections). Backend auto-detects what changed vs original and logs corrections.

**Request**:
```json
{ "form_data": { "section_a.member_name": { "value": "Smith, John, A", "confidence": "high", "needs_review": false, "reason": null }, ... } }
```

**Response** (`FormUpdateResponse`):
```json
{ "corrections_count": 3, "form": { ...FormResponse } }
```

#### 5. `GET /api/forms/{form_id}/pdf`
Download the filled PDF. Returns the "Request for Approval of Services" PDF template with all form field values written on it.

**Response**: Binary PDF file (`application/pdf`) with `Content-Disposition: attachment` header.

**Usage**: Open in new tab or trigger download:
```typescript
window.open(`${API_BASE}/api/forms/${formId}/pdf`, '_blank');
```

#### 6. `PUT /api/forms/{form_id}/approve`
Mark form as approved.

**Response**:
```json
{ "status": "approved", "approved_at": "2026-03-16T..." }
```

#### 7. `GET /api/analytics/accuracy`
```json
{
  "global_accuracy": 0.85,
  "by_field_section": { "section_a": 3, "section_d": 5 },
  "by_doc_type": { "insurance_card": 2, "clinical_note": 4 },
  "by_confidence": { "high": 1, "medium": 3, "low": 4 },
  "total_forms": 10,
  "total_corrections": 15
}
```

#### 8. `GET /api/analytics/ai-usage`
```json
{
  "total_cost_usd": 0.0234,
  "total_tokens": 45000,
  "avg_tokens_per_doc": 5000.0,
  "avg_duration_ms": 3200.0,
  "by_doc_type": { "insurance_card": { "count": 3, "tokens": 15000, "cost": 0.01 } },
  "by_model": { "gpt-4o-mini": { "count": 9, "tokens": 45000, "cost": 0.0234 } },
  "recent_calls": [{ "id": "...", "document_id": "...", "doc_type": "...", "total_tokens": 5000, "estimated_cost": 0.003, "duration_ms": 2800, "status": "success" }]
}
```

## Field Structure (Critical)

Every field from the AI has this structure:
```json
{
  "value": "string or null",
  "confidence": "high|medium|low|missing",
  "needs_review": true/false,
  "reason": "string or null"
}
```

Fields are keyed as `section.field_name` in the `form_data` dict. For example:
- `header.payer`
- `section_a.member_name`
- `section_b.provider_npi`
- `section_e.medications.0.medication`
- `section_e.medications.0.dose`
- `section_e.assessment_tools.1.score`

## Form Sections and Fields

### Header
- `header.payer` — Insurance payer name
- `header.date_of_request` — Date of request
- `header.payer_fax` — Payer fax number
- `header.payer_phone` — Payer phone number

### Section A: Member Information
- `section_a.member_name` — Member name (Last, First, MI)
- `section_a.date_of_birth`
- `section_a.gender`
- `section_a.member_id`
- `section_a.group_number`
- `section_a.phone_number`
- `section_a.address`

### Section B: Requesting Provider Information
- `section_b.provider_name`
- `section_b.provider_npi`
- `section_b.facility_practice_name`
- `section_b.tax_id`
- `section_b.phone`
- `section_b.fax`
- `section_b.address`

### Section C: Referring Provider (if different)
- `section_c.referring_provider_name`
- `section_c.referring_provider_npi`
- `section_c.phone`

### Section D: Service Information
- `section_d.type_of_service` — One of: Outpatient, Inpatient, Intensive Outpatient, Partial Hospitalization, Residential, Other
- `section_d.service_setting`
- `section_d.cpt_hcpcs_codes` — Comma-separated
- `section_d.icd10_diagnosis_codes` — Comma-separated
- `section_d.diagnosis_descriptions`
- `section_d.requested_start_date`
- `section_d.requested_end_date`
- `section_d.number_of_sessions`
- `section_d.frequency`

### Section E: Clinical Information
- `section_e.presenting_symptoms` — Textarea
- `section_e.relevant_clinical_history` — Textarea
- `section_e.medications.{index}.medication` — Table rows
- `section_e.medications.{index}.dose`
- `section_e.medications.{index}.frequency`
- `section_e.medications.{index}.prescriber`
- `section_e.assessment_tools.{index}.tool` — Table rows
- `section_e.assessment_tools.{index}.score`
- `section_e.assessment_tools.{index}.date`
- `section_e.treatment_goals` — Textarea

### Section F: Clinical Justification
- `section_f.medical_necessity` — Textarea: "Why is this level of care medically necessary?"
- `section_f.risk_if_not_provided` — Textarea: "What is the risk if services are not provided?"

### Section G: Attestation
- `section_g.provider_signature`
- `section_g.printed_name`
- `section_g.date`
- `section_g.license_number`

## UI Flow (3 Steps)

### Step 1: Upload Documents
- Drag-and-drop zone or file picker (max 6 files, PDF/PNG/JPG, max 10MB each)
- Show thumbnail previews of uploaded documents using the `thumbnails` URLs from the upload response
- "Extract Data" button that calls `POST /api/documents/extract`
- Show loading spinner during extraction (it takes 5-15 seconds)

### Step 2: Review & Edit Form
This is the MAIN screen. After extraction, show the form organized by sections A-G.

**For each field:**
- Show the field label and an editable input
- Color-code by confidence:
  - HIGH = green left border or subtle green background
  - MEDIUM = yellow/amber
  - LOW = red/orange
  - MISSING = gray, empty input with placeholder
- If `needs_review` is true, show a small warning icon or highlight
- If `reason` exists, show it as a tooltip on hover
- User can edit any field value directly

**For table fields (medications, assessment_tools):**
- Render as editable tables
- Allow adding/removing rows

**Sidebar or panel:**
- Show source document thumbnails/images so the user can reference them while reviewing
- Clicking a thumbnail opens a larger view (modal or side panel)

**Confidence summary bar:**
- Show the confidence breakdown (high/medium/low/missing counts) at the top

**Actions:**
- "Save Changes" button → `PUT /api/forms/{form_id}` with current form_data
- "Download PDF" button → `GET /api/forms/{form_id}/pdf` — opens/downloads the filled PDF in a new tab. This generates the real "Request for Approval of Services" PDF with all field values written on the template. Available at any time (draft, in_review, or approved).
- "Approve" button → `PUT /api/forms/{form_id}/approve`

### Step 3: Confirmation
- Show "Form approved!" success state
- Show summary of corrections made (corrections_count from the update response)
- Show prominent "Download Final PDF" button → `GET /api/forms/{form_id}/pdf`

## Additional Pages

### Analytics Dashboard (optional but nice)
- Route: `/analytics`
- Shows global accuracy, corrections by section, AI usage/cost
- Uses `GET /api/analytics/accuracy` and `GET /api/analytics/ai-usage`

## Design Guidelines

- Clean, professional medical/healthcare look
- White background, subtle gray borders, blue accents
- The form should visually resemble a real paper form — section headers like "Section A: Member Information", clean grid layout
- Responsive but primarily desktop-focused (1200px+ screens)
- Use shadcn/ui components: Card, Input, Label, Button, Badge, Tooltip, Dialog, Table, Tabs, Progress
- Confidence colors: green (#22c55e), amber (#f59e0b), red (#ef4444), gray (#9ca3af)

## Project Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tailwind.config.js
├── tsconfig.json
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── api/
│   │   └── client.ts          # axios/fetch wrapper, base URL config
│   ├── types/
│   │   └── index.ts           # TypeScript types matching backend schemas
│   ├── components/
│   │   ├── upload/
│   │   │   └── UploadZone.tsx
│   │   ├── form/
│   │   │   ├── FormReview.tsx       # Main form review container
│   │   │   ├── FormSection.tsx      # Renders one section (A, B, C, etc.)
│   │   │   ├── FieldInput.tsx       # Single field with confidence indicator
│   │   │   ├── MedicationsTable.tsx # Editable medications table
│   │   │   ├── AssessmentTable.tsx  # Editable assessment tools table
│   │   │   └── ConfidenceBar.tsx    # Summary bar
│   │   ├── documents/
│   │   │   └── DocumentViewer.tsx   # Source document preview panel
│   │   └── analytics/
│   │       └── Dashboard.tsx
│   ├── pages/
│   │   ├── HomePage.tsx
│   │   └── AnalyticsPage.tsx
│   └── lib/
│       └── utils.ts
```

## Important Implementation Notes

1. **Do NOT use Supabase client in the frontend** — all data goes through the FastAPI backend
2. **CORS is configured** — the backend allows `http://localhost:3000`
3. **Field keys use dot notation** — `section_a.member_name`, not nested objects. The `form_data` from the API is a flat dict with dot-notation keys
4. **Table fields** use indexed dot notation: `section_e.medications.0.medication`. You'll need to parse these to render as tables and flatten them back when saving
5. **Confidence drives the UX** — this is the core value proposition. Make confidence visual and obvious
6. **The "reason" field** is important context for reviewers — always show it (tooltip, small text, etc.)
7. When saving, send back ALL fields (not just changed ones) to `PUT /api/forms/{form_id}`
