from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# Menggunakan satu standar Config untuk semua class (Pydantic v2)
common_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

# 1. Exercise Schemas
class ExerciseResponse(BaseModel):
    id: UUID  # Gunakan UUID di sini
    name: str
    target_muscle: str

    model_config = common_config

class ExerciseCreate(BaseModel):
    name: str
    target_muscle: str

# 2. Workout Set Schemas
class WorkoutSetCreate(BaseModel):
    exercise_id: UUID
    set_number: int = Field(..., description="Set ke-berapa", example=1)
    weight_kg: float = Field(..., description="Beban angkatan", example=60.0)
    reps: int = Field(..., description="Jumlah repetisi", example=10)
    set_type: str = Field(default="normal", description="Tipe set")

class WorkoutSetResponse(BaseModel):
    id: UUID
    session_id: UUID
    exercise_id: UUID
    exercise_name: Optional[str] = None
    set_number: int
    weight_kg: float
    reps: int
    set_type: str
    is_pr: bool 

    model_config = common_config

# 3. Workout Session Schemas
class WorkoutSessionCreate(BaseModel):
    title: Optional[str] = Field(default="Sore Workout Session", example="Push Day Heavy")
    duration_minutes: Optional[int] = Field(default=0, description="Duration in minutes")
    start_time: Optional[datetime] = Field(default=None, description="Custom start time for retroactive logging")
    end_time: Optional[datetime] = Field(default=None, description="Custom end time for retroactive logging")
    sets: List[WorkoutSetCreate] = Field(..., description="Array kumpulan set")

class WorkoutSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_minutes: Optional[int]
    sets: List[WorkoutSetResponse] = [] 

    model_config = common_config