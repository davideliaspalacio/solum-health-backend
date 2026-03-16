import time
from app.config import get_supabase, GPT_INPUT_COST_PER_1M, GPT_OUTPUT_COST_PER_1M
from app.models.schemas import AIUsageLog, AIStatus


async def track_ai_call(
    document_id: str | None,
    doc_type: str | None,
    page_number: int | None,
    ai_response,
) -> AIUsageLog:
    """
    Extract usage info from OpenAI response and save to ai_usage_logs.
    Call this AFTER a successful GPT call with the response object.
    """
    usage = ai_response.usage

    input_tokens = usage.prompt_tokens
    output_tokens = usage.completion_tokens
    total_tokens = usage.total_tokens

    # Cost calculation: GPT-4o-mini pricing
    estimated_cost = (
        (input_tokens * GPT_INPUT_COST_PER_1M / 1_000_000)
        + (output_tokens * GPT_OUTPUT_COST_PER_1M / 1_000_000)
    )

    log = AIUsageLog(
        document_id=document_id,
        doc_type=doc_type,
        page_number=page_number,
        model=ai_response.model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost=round(estimated_cost, 6),
        status=AIStatus.SUCCESS,
    )

    # Save to Supabase
    sb = get_supabase()
    sb.table("ai_usage_logs").insert(log.model_dump()).execute()

    return log


async def track_ai_error(
    document_id: str | None,
    doc_type: str | None,
    page_number: int | None,
    error_message: str,
    duration_ms: int = 0,
) -> AIUsageLog:
    """Track a failed AI call."""
    log = AIUsageLog(
        document_id=document_id,
        doc_type=doc_type,
        page_number=page_number,
        status=AIStatus.ERROR,
        error_message=error_message,
        duration_ms=duration_ms,
    )

    sb = get_supabase()
    sb.table("ai_usage_logs").insert(log.model_dump()).execute()

    return log
