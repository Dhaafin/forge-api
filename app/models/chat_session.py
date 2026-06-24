import uuid
import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

class AIChatSession(Base):
    __tablename__ = "ai_chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, default="New Consultation", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    
    messages = relationship("AIChatMessage", back_populates="session", cascade="all, delete-orphan")
