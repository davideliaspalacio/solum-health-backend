from app.models.schemas import (
    ExtractionResult,
    ExtractedField,
    ConfidenceLevel,
    ConfidenceSummary,
    MedicationEntry,
    AssessmentEntry,
)
from app.config import DOC_TYPE_PRIORITY

SECTION_NAMES = ["header", "section_a", "section_b", "section_c", "section_d", "section_e", "section_f", "section_g"]


def _get_all_fields(extraction: ExtractionResult) -> dict[str, ExtractedField]:
    """Flatten all sections into {section.field_name: ExtractedField}.

    For table fields (medications, assessment_tools), each entry is flattened as:
      section_e.medications.0.medication, section_e.medications.0.dose, etc.
    """
    fields = {}
    for section_name in SECTION_NAMES:
        section = getattr(extraction, section_name)
        for field_name, field_value in section:
            if isinstance(field_value, list):
                # Handle table fields (medications, assessment_tools)
                for i, entry in enumerate(field_value):
                    for sub_field_name, sub_field_value in entry:
                        key = f"{section_name}.{field_name}.{i}.{sub_field_name}"
                        fields[key] = sub_field_value
            elif isinstance(field_value, ExtractedField):
                key = f"{section_name}.{field_name}"
                fields[key] = field_value
    return fields


def _resolve_conflict(
    values: list[tuple[ExtractedField, str, int]],
) -> ExtractedField:
    """
    values = list of (field, doc_type, priority).
    Pick the one from the highest priority doc (lowest number).
    Mark as LOW confidence with CONFLICT reason.
    """
    sorted_vals = sorted(values, key=lambda x: x[2])
    winner = sorted_vals[0]
    return ExtractedField(
        value=winner[0].value,
        confidence=ConfidenceLevel.LOW,
        needs_review=True,
        reason=f"Conflict: {len(values)} docs disagree. Using {winner[1]} (priority {winner[2]}). "
        f"Alternatives: {', '.join(v[0].value or 'null' for v in sorted_vals[1:])}",
    )


def merge_extractions(
    extractions: list[tuple[ExtractionResult, str]],
) -> tuple[dict, ConfidenceSummary]:
    """
    Merge multiple document extractions into a single form.

    Args:
        extractions: list of (ExtractionResult, doc_type) tuples

    Returns:
        (merged_fields_dict, confidence_summary)
    """
    if not extractions:
        return {}, ConfidenceSummary()

    # Collect all field keys from all extractions
    all_field_maps = []
    for extraction, doc_type in extractions:
        fields = _get_all_fields(extraction)
        priority = DOC_TYPE_PRIORITY.get(doc_type, 99)
        all_field_maps.append((fields, doc_type, priority))

    # Get union of all field keys
    all_keys = set()
    for fields, _, _ in all_field_maps:
        all_keys.update(fields.keys())

    merged = {}
    summary = ConfidenceSummary()

    for key in sorted(all_keys):
        # Collect non-null values for this field from all docs
        values_with_meta = []
        for fields, doc_type, priority in all_field_maps:
            field = fields.get(key)
            if field and field.value is not None and field.confidence != ConfidenceLevel.MISSING:
                values_with_meta.append((field, doc_type, priority))

        if len(values_with_meta) == 0:
            # No docs have this field
            merged[key] = ExtractedField(
                value=None,
                confidence=ConfidenceLevel.MISSING,
                needs_review=True,
                reason="Not found in any document",
            ).model_dump()
            summary.missing += 1

        elif len(values_with_meta) == 1:
            # Single doc — use as-is
            field = values_with_meta[0][0]
            if field.confidence != ConfidenceLevel.HIGH:
                field = field.model_copy(update={"needs_review": True})
            merged[key] = field.model_dump()
            _count_confidence(summary, field.confidence)

        else:
            # Multiple docs — check if they agree
            unique_values = set(v[0].value for v in values_with_meta)

            if len(unique_values) == 1:
                # All agree — boost to HIGH
                merged[key] = ExtractedField(
                    value=values_with_meta[0][0].value,
                    confidence=ConfidenceLevel.HIGH,
                    needs_review=False,
                    reason=f"Confirmed by {len(values_with_meta)} documents",
                ).model_dump()
                summary.high += 1
            else:
                # Conflict — use highest priority doc
                resolved = _resolve_conflict(values_with_meta)
                merged[key] = resolved.model_dump()
                summary.low += 1

    return merged, summary


def _count_confidence(summary: ConfidenceSummary, level: ConfidenceLevel):
    if level == ConfidenceLevel.HIGH:
        summary.high += 1
    elif level == ConfidenceLevel.MEDIUM:
        summary.medium += 1
    elif level == ConfidenceLevel.LOW:
        summary.low += 1
    else:
        summary.missing += 1
