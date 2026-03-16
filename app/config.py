import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")

# GPT-4o-mini pricing (per 1M tokens)
GPT_INPUT_COST_PER_1M = 0.15
GPT_OUTPUT_COST_PER_1M = 0.60
GPT_MODEL = "gpt-4o-mini"

# File upload limits
MAX_FILES = 6
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}

# Document type priority for conflict resolution
DOC_TYPE_PRIORITY = {
    "insurance_card": 1,
    "intake_form": 2,
    "referral_letter": 3,
    "clinical_note": 4,
    "lab_results": 5,
    "handwritten_note": 6,
}


def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)
