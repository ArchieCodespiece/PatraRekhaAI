
# ============================================================================
# HEALTH
# ============================================================================

from fastapi import APIRouter


router = APIRouter()


@router.get("/health")
def health():
    return {
        "ok": True,
        "service": "PatraRekha API",
    }