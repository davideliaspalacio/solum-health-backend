from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import FRONTEND_URL
from app.routers import documents, forms, analytics

app = FastAPI(
    title="Solum Health API",
    description="Document Extraction & Form Auto-Fill",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Routers
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(forms.router, prefix="/api/forms", tags=["Forms"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Solum Health API"}
