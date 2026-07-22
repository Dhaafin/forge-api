import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="user")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Profile Customization Fields
    preferred_unit = Column(String, default="metric", nullable=False)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)
    fitness_goal = Column(String, nullable=True)
    experience_level = Column(String, nullable=True)
    injuries_or_limitations = Column(String, nullable=True)