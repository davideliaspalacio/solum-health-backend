import io
import textwrap
from pathlib import Path

import fitz  # PyMuPDF

TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "07-service-request-form.pdf"

FONT_NAME = "Courier"
FONT_SIZE = 9
FONT_SIZE_SMALL = 8
FONT_COLOR = (0, 0, 0)

# Checkbox X positions for type_of_service
CHECKBOX_POSITIONS = {
    "Outpatient": (64, 518),
    "Inpatient": (119, 518),
    "Intensive Outpatient": (169, 518),
    "Partial Hospitalization": (255, 518),
    "Residential": (345, 518),
    "Other": (403, 518),
}

# Page 1 field mappings: field_key -> (x, y)
PAGE1_FIELDS = {
    # Header
    "header.payer": (84, 73),
    "header.date_of_request": (374, 73),
    "header.payer_fax": (100, 91),
    "header.payer_phone": (362, 91),
    # Section A
    "section_a.member_name": (178, 121),
    "section_a.date_of_birth": (112, 139),
    "section_a.gender": (92, 157),
    "section_a.member_id": (105, 175),
    "section_a.group_number": (120, 193),
    "section_a.phone_number": (120, 211),
    "section_a.address": (96, 229),
    # Section B
    "section_b.provider_name": (120, 273),
    "section_b.provider_npi": (112, 291),
    "section_b.facility_practice_name": (149, 309),
    "section_b.tax_id": (88, 327),
    "section_b.phone": (88, 345),
    "section_b.fax": (78, 363),
    "section_b.address": (96, 381),
    # Section C
    "section_c.referring_provider_name": (158, 425),
    "section_c.referring_provider_npi": (150, 443),
    "section_c.phone": (88, 461),
    # Section D (except type_of_service which uses checkboxes)
    "section_d.service_setting": (122, 527),
    "section_d.cpt_hcpcs_codes": (142, 545),
    "section_d.icd10_diagnosis_codes": (162, 563),
    "section_d.diagnosis_descriptions": (158, 581),
    "section_d.requested_start_date": (145, 599),
    "section_d.requested_end_date": (142, 617),
    "section_d.number_of_sessions": (163, 635),
    "section_d.frequency": (104, 653),
}

# Page 2 simple fields: field_key -> (x, y)
PAGE2_FIELDS = {
    "section_g.provider_signature": (133, 647),
    "section_g.printed_name": (113, 667),
    "section_g.date": (79, 687),
    "section_g.license_number": (98, 707),
}

# Page 2 textarea fields: field_key -> (x_start, y_start, max_width, max_lines)
PAGE2_TEXTAREAS = {
    "section_e.presenting_symptoms": (55, 76, 500, 4),
    "section_e.relevant_clinical_history": (55, 150, 500, 4),
    "section_e.treatment_goals": (55, 364, 500, 3),
    "section_f.medical_necessity": (55, 448, 500, 5),
    "section_f.risk_if_not_provided": (55, 538, 500, 3),
}

# Table configs
MEDICATIONS_TABLE = {
    "y_start": 236,
    "row_height": 16,
    "max_rows": 4,
    "columns": {
        "medication": 55,
        "dose": 183,
        "frequency": 310,
        "prescriber": 437,
    },
}

ASSESSMENT_TABLE = {
    "y_start": 314,
    "row_height": 16,
    "max_rows": 3,
    "columns": {
        "tool": 55,
        "score": 225,
        "date": 395,
    },
}


def _get_value(form_data: dict, key: str) -> str | None:
    """Extract the value string from a form_data field."""
    field = form_data.get(key)
    if field is None:
        return None
    if isinstance(field, dict):
        return field.get("value")
    return str(field)


def _insert_text(page: fitz.Page, x: float, y: float, text: str, font_size: float = FONT_SIZE):
    """Insert text at exact position on a page."""
    page.insert_text(
        (x, y),
        text,
        fontname="cour",
        fontsize=font_size,
        color=FONT_COLOR,
    )


def _insert_textarea(page: fitz.Page, x: float, y: float, text: str, max_width: int, max_lines: int):
    """Insert wrapped text as a textarea block."""
    chars_per_line = max_width // 5  # approximate chars for Courier 8pt
    lines = textwrap.wrap(text, width=chars_per_line)
    for i, line in enumerate(lines[:max_lines]):
        _insert_text(page, x, y + (i * 16), line, FONT_SIZE_SMALL)


def fill_pdf(form_data: dict) -> bytes:
    """
    Fill the service request form PDF template with form data.

    Args:
        form_data: flat dict with dot-notation keys, each value is
                   {"value": "...", "confidence": "...", ...}

    Returns:
        Filled PDF as bytes.
    """
    doc = fitz.open(str(TEMPLATE_PATH))
    page1 = doc[0]
    page2 = doc[1]

    # --- Page 1: Simple fields ---
    for key, (x, y) in PAGE1_FIELDS.items():
        value = _get_value(form_data, key)
        if value:
            _insert_text(page1, x, y, value)

    # --- Page 1: Type of service checkbox ---
    tos_value = _get_value(form_data, "section_d.type_of_service")
    if tos_value:
        for label, (cx, cy) in CHECKBOX_POSITIONS.items():
            if label.lower() in tos_value.lower():
                _insert_text(page1, cx, cy, "X", 10)
                break

    # --- Page 2: Simple fields (Section G) ---
    for key, (x, y) in PAGE2_FIELDS.items():
        value = _get_value(form_data, key)
        if value:
            _insert_text(page2, x, y, value)

    # --- Page 2: Textareas ---
    for key, (x, y, max_w, max_l) in PAGE2_TEXTAREAS.items():
        value = _get_value(form_data, key)
        if value:
            _insert_textarea(page2, x, y, value, max_w, max_l)

    # --- Page 2: Medications table ---
    med_cfg = MEDICATIONS_TABLE
    for i in range(med_cfg["max_rows"]):
        row_y = med_cfg["y_start"] + (i * med_cfg["row_height"])
        has_data = False
        for col_name, col_x in med_cfg["columns"].items():
            value = _get_value(form_data, f"section_e.medications.{i}.{col_name}")
            if value:
                _insert_text(page2, col_x, row_y, value, FONT_SIZE_SMALL)
                has_data = True
        if not has_data:
            break

    # --- Page 2: Assessment tools table ---
    assess_cfg = ASSESSMENT_TABLE
    for i in range(assess_cfg["max_rows"]):
        row_y = assess_cfg["y_start"] + (i * assess_cfg["row_height"])
        has_data = False
        for col_name, col_x in assess_cfg["columns"].items():
            value = _get_value(form_data, f"section_e.assessment_tools.{i}.{col_name}")
            if value:
                _insert_text(page2, col_x, row_y, value, FONT_SIZE_SMALL)
                has_data = True
        if not has_data:
            break

    # Write to bytes
    output = io.BytesIO()
    doc.save(output)
    doc.close()
    output.seek(0)
    return output.read()
