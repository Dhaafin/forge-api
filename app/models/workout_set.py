import uuid
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean,Float
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class WorkoutSet(Base):
    __tablename__ = "workout_sets"
    
    id = Column(UUID(as_uuid=True), default=uuid.uuid4, primary_key=True, index=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("workout_sessions.id", ondelete="CASCADE"), nullable=False)
    exercise_id = Column(UUID(as_uuid=True), ForeignKey("exercises.id", ondelete="CASCADE"), nullable=False)
    
    set_number = Column(Integer, nullable=False)
    weight_kg = Column(Float, nullable=False)
    reps = Column(Integer, nullable=False)
    
    set_type = Column(String, default="normal")
    is_pr = Column(Boolean, default=False, nullable=False)
    