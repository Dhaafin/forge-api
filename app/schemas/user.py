from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    preferred_unit: Optional[str] = Field(None, description="Must be 'metric' or 'imperial'")
    weight_kg: Optional[float] = Field(None, ge=0, le=500)
    height_cm: Optional[float] = Field(None, ge=0, le=300)
    fitness_goal: Optional[str] = Field(None, description="e.g. 'build_muscle', 'lose_fat', 'increase_strength', 'endurance', 'general_health'")
    experience_level: Optional[str] = Field(None, description="e.g. 'beginner', 'intermediate', 'advanced'")
    injuries_or_limitations: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("Name cannot be empty or just whitespace.")
            return stripped
        return v

    @field_validator("preferred_unit")
    @classmethod
    def validate_preferred_unit(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            if v not in ("metric", "imperial"):
                raise ValueError("preferred_unit must be 'metric' or 'imperial'")
        return v

    @field_validator("fitness_goal")
    @classmethod
    def validate_fitness_goal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_goals = ("build_muscle", "lose_fat", "increase_strength", "endurance", "general_health")
            if v not in valid_goals:
                raise ValueError(f"fitness_goal must be one of {valid_goals}")
        return v

    @field_validator("experience_level")
    @classmethod
    def validate_experience_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            valid_levels = ("beginner", "intermediate", "advanced")
            if v not in valid_levels:
                raise ValueError(f"experience_level must be one of {valid_levels}")
        return v


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime
    preferred_unit: str
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    fitness_goal: Optional[str] = None
    experience_level: Optional[str] = None
    injuries_or_limitations: Optional[str] = None

    class Config:
        from_attributes = True
