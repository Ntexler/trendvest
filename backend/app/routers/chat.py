"""
Chat API endpoint for TrendVest AI Explainer.
"""
from fastapi import APIRouter, Request, HTTPException
from ..models.schemas import ChatRequest, ChatResponse
from ..services.ai_explainer import AIExplainer

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Singleton explainer instance
explainer = AIExplainer()


@router.post("", response_model=ChatResponse)
async def ask_ai(request: Request, body: ChatRequest):
    """
    Ask the AI explainer a financial question in Hebrew.

    Rate limited: 3 questions/day for free tier (by IP).
    """
    # Use IP for rate limiting (replace with user_id when auth is added)
    client_ip = request.client.host if request.client else "unknown"
    user_id = client_ip

    # Check rate limit
    allowed, remaining = explainer.check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "error": "הגעת למגבלת השאלות היומית",
                "remaining": 0,
                "message": "3 שאלות ביום בחינם. שדרג ל-Pro לגישה ללא הגבלה.",
            }
        )

    result = await explainer.ask(
        question=body.question,
        context=body.context,
        user_id=user_id,
    )

    return ChatResponse(
        answer=result["answer"],
        suggested_questions=result["suggested_questions"],
        questions_remaining=result["questions_remaining"],
    )


@router.get("/remaining")
async def get_remaining(request: Request):
    """Check how many questions the user has left today."""
    client_ip = request.client.host if request.client else "unknown"
    _, remaining = explainer.check_rate_limit(client_ip)
    return {"remaining": remaining, "daily_limit": explainer.free_daily_limit}
