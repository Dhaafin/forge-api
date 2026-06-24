from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.ai_coach import AICoachRequest, AICoachResponse, AIChatRequest
from app.services.ai_service import generate_coach_analysis, generate_rag_stream_response

router = APIRouter()

@router.post("/coach", response_model=AICoachResponse, status_code=status.HTTP_200_OK)
async def get_workout_ai_analysis(
    payload: AICoachRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate or retrieve cached AI Coach workout feedback and progressive overload advice.
    Runs analysis strictly in English.
    """
    return await generate_coach_analysis(
        session_id=payload.session_id,
        db=db,
        user=current_user
    )


@router.post("/chat/stream", status_code=status.HTTP_200_OK)
async def chat_stream(
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stream RAG answers for questions on exercise guides.
    """
    return StreamingResponse(
        generate_rag_stream_response(
            query=payload.message,
            db=db,
            user=current_user
        ),
        media_type="text/plain"
    )

