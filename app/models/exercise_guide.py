import uuid
from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class ExerciseGuide(Base):
    __tablename__ = "exercise_guides"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    exercise_name = Column(String, unique=True, index=True, nullable=False)
    description = Column(Text, nullable=False)
    target_muscle = Column(String, index=True, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
