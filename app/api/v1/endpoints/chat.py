from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
from typing import List

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.chat_session import AIChatSession
from app.models.chat_message import AIChatMessage
from app.schemas.ai_coach import AIChatSessionResponse, AIChatMessageResponse, AIChatRequest
from app.services.ai_service import generate_rag_stream_response

router = APIRouter()

@router.post("/sessions", response_model=AIChatSessionResponse, status_code=status.HTTP_201_CREATED)
def create_chat_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new AI chat session for the current user.
    """
    session = AIChatSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session

@router.get("/sessions", response_model=List[AIChatSessionResponse], status_code=status.HTTP_200_OK)
def list_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all chat sessions for the current user.
    """
    sessions = (
        db.query(AIChatSession)
        .filter(AIChatSession.user_id == current_user.id)
        .order_by(AIChatSession.created_at.desc())
        .all()
    )
    return sessions

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a specific chat session and all its messages.
    """
    session = (
        db.query(AIChatSession)
        .filter(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or unauthorized."
        )
    db.delete(session)
    db.commit()
    return

@router.get("/sessions/{session_id}/messages", response_model=List[AIChatMessageResponse], status_code=status.HTTP_200_OK)
def get_chat_messages(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get full message history for a specific chat session.
    """
    session = (
        db.query(AIChatSession)
        .filter(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or unauthorized."
        )
    
    messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.session_id == session_id)
        .order_by(AIChatMessage.created_at.asc())
        .all()
    )
    return messages

@router.post("/sessions/{session_id}/stream", status_code=status.HTTP_200_OK)
async def chat_stream_with_history(
    session_id: UUID,
    payload: AIChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Stream RAG assistant response for a message in an existing chat session.
    Automatically logs query and response to database.
    """
    session = (
        db.query(AIChatSession)
        .filter(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id)
        .first()
    )
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found or unauthorized."
        )

    return StreamingResponse(
        generate_rag_stream_response(
            query=payload.message,
            db=db,
            user=current_user,
            session_id=session_id
        ),
        media_type="text/plain"
    )
