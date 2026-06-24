import uuid
import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class AIChatMessage(Base):
    __tablename__ = "ai_chat_messages"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String, nullable=False)  # "user" or "ai"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    session = relationship("AIChatSession", back_populates="messages")
