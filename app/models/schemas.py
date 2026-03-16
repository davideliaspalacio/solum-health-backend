from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


# --- Enums ---

class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MISSING = "missing"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    ERROR = "error"


class FormStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class AIStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


# --- Extracted Field (single field from AI) ---

class ExtractedField(BaseModel):
    value: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.MISSING
    needs_review: bool = True
    reason: Optional[str] = None


# --- Table entry models ---

class MedicationEntry(BaseModel):
    medication: ExtractedField = Field(default_factory=ExtractedField)
    dose: ExtractedField = Field(default_factory=ExtractedField)
    frequency: ExtractedField = Field(default_factory=ExtractedField)
    prescriber: ExtractedField = Field(default_factory=ExtractedField)


class AssessmentEntry(BaseModel):
    tool: ExtractedField = Field(default_factory=ExtractedField)
    score: ExtractedField = Field(default_factory=ExtractedField)
    date: ExtractedField = Field(default_factory=ExtractedField)


# --- Form Sections (aligned to "Request for Approval of Services" form) ---

class HeaderFields(BaseModel):
    payer: ExtractedField = Field(default_factory=ExtractedField)
    date_of_request: ExtractedField = Field(default_factory=ExtractedField)
    payer_fax: ExtractedField = Field(default_factory=ExtractedField)
    payer_phone: ExtractedField = Field(default_factory=ExtractedField)


class SectionAMemberInfo(BaseModel):
    member_name: ExtractedField = Field(default_factory=ExtractedField)
    date_of_birth: ExtractedField = Field(default_factory=ExtractedField)
    gender: ExtractedField = Field(default_factory=ExtractedField)
    member_id: ExtractedField = Field(default_factory=ExtractedField)
    group_number: ExtractedField = Field(default_factory=ExtractedField)
    phone_number: ExtractedField = Field(default_factory=ExtractedField)
    address: ExtractedField = Field(default_factory=ExtractedField)


class SectionBRequestingProvider(BaseModel):
    provider_name: ExtractedField = Field(default_factory=ExtractedField)
    provider_npi: ExtractedField = Field(default_factory=ExtractedField)
    facility_practice_name: ExtractedField = Field(default_factory=ExtractedField)
    tax_id: ExtractedField = Field(default_factory=ExtractedField)
    phone: ExtractedField = Field(default_factory=ExtractedField)
    fax: ExtractedField = Field(default_factory=ExtractedField)
    address: ExtractedField = Field(default_factory=ExtractedField)


class SectionCReferringProvider(BaseModel):
    referring_provider_name: ExtractedField = Field(default_factory=ExtractedField)
    referring_provider_npi: ExtractedField = Field(default_factory=ExtractedField)
    phone: ExtractedField = Field(default_factory=ExtractedField)


class SectionDServiceInfo(BaseModel):
    type_of_service: ExtractedField = Field(default_factory=ExtractedField)
    service_setting: ExtractedField = Field(default_factory=ExtractedField)
    cpt_hcpcs_codes: ExtractedField = Field(default_factory=ExtractedField)
    icd10_diagnosis_codes: ExtractedField = Field(default_factory=ExtractedField)
    diagnosis_descriptions: ExtractedField = Field(default_factory=ExtractedField)
    requested_start_date: ExtractedField = Field(default_factory=ExtractedField)
    requested_end_date: ExtractedField = Field(default_factory=ExtractedField)
    number_of_sessions: ExtractedField = Field(default_factory=ExtractedField)
    frequency: ExtractedField = Field(default_factory=ExtractedField)


class SectionEClinicalInfo(BaseModel):
    presenting_symptoms: ExtractedField = Field(default_factory=ExtractedField)
    relevant_clinical_history: ExtractedField = Field(default_factory=ExtractedField)
    medications: list[MedicationEntry] = Field(default_factory=list)
    assessment_tools: list[AssessmentEntry] = Field(default_factory=list)
    treatment_goals: ExtractedField = Field(default_factory=ExtractedField)


class SectionFClinicalJustification(BaseModel):
    medical_necessity: ExtractedField = Field(default_factory=ExtractedField)
    risk_if_not_provided: ExtractedField = Field(default_factory=ExtractedField)


class SectionGAttestation(BaseModel):
    provider_signature: ExtractedField = Field(default_factory=ExtractedField)
    printed_name: ExtractedField = Field(default_factory=ExtractedField)
    date: ExtractedField = Field(default_factory=ExtractedField)
    license_number: ExtractedField = Field(default_factory=ExtractedField)


class ExtractionResult(BaseModel):
    doc_type: Optional[str] = None
    header: HeaderFields = Field(default_factory=HeaderFields)
    section_a: SectionAMemberInfo = Field(default_factory=SectionAMemberInfo)
    section_b: SectionBRequestingProvider = Field(default_factory=SectionBRequestingProvider)
    section_c: SectionCReferringProvider = Field(default_factory=SectionCReferringProvider)
    section_d: SectionDServiceInfo = Field(default_factory=SectionDServiceInfo)
    section_e: SectionEClinicalInfo = Field(default_factory=SectionEClinicalInfo)
    section_f: SectionFClinicalJustification = Field(default_factory=SectionFClinicalJustification)
    section_g: SectionGAttestation = Field(default_factory=SectionGAttestation)


# --- Confidence Summary ---

class ConfidenceSummary(BaseModel):
    high: int = 0
    medium: int = 0
    low: int = 0
    missing: int = 0


# --- API Request/Response Models ---

# Documents
class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_url: str
    image_urls: list[str] = []
    doc_type: Optional[str] = None
    status: DocumentStatus
    page_count: int = 1
    file_size_bytes: Optional[int] = None
    created_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    document_ids: list[str]
    thumbnails: list[str]


class ExtractRequest(BaseModel):
    document_ids: list[str]


class ExtractResponse(BaseModel):
    form_id: str
    merged_data: dict
    confidence: ConfidenceSummary


# Forms
class FormResponse(BaseModel):
    id: str
    form_type: str
    form_data: dict
    original_form_data: Optional[dict] = None
    status: FormStatus
    confidence_summary: Optional[ConfidenceSummary] = None
    source_documents: list[DocumentResponse] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None


class FormUpdateRequest(BaseModel):
    form_data: dict


class FormUpdateResponse(BaseModel):
    corrections_count: int
    form: FormResponse


class FormApproveResponse(BaseModel):
    status: FormStatus
    approved_at: datetime


# Corrections
class CorrectionResponse(BaseModel):
    id: str
    field_name: str
    field_section: Optional[str] = None
    original_value: Optional[str] = None
    corrected_value: str
    original_confidence: Optional[str] = None
    corrected_at: Optional[datetime] = None


# Analytics
class AccuracyResponse(BaseModel):
    global_accuracy: float
    by_field_section: dict
    by_doc_type: dict
    by_confidence: dict
    total_forms: int
    total_corrections: int


class AIUsageResponse(BaseModel):
    total_cost_usd: float
    total_tokens: int
    avg_tokens_per_doc: float
    avg_duration_ms: float
    by_doc_type: dict
    by_model: dict
    recent_calls: list[dict]


# AI Tracker
class AIUsageLog(BaseModel):
    document_id: Optional[str] = None
    doc_type: Optional[str] = None
    page_number: Optional[int] = None
    model: str = "gpt-4o-mini"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    duration_ms: int = 0
    status: AIStatus = AIStatus.SUCCESS
    error_message: Optional[str] = None
    fields_extracted: int = 0
    fields_total: int = 0
    avg_confidence: float = 0.0
