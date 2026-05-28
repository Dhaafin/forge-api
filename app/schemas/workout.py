# app/schemas/workout.py
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# Database Schemas
class ExerciseResponse(BaseModel):
    id: UUID
    name: str
    target_muscle: str

    class Config:
        from_attributes = True


# Workout Schemas
class WorkoutSetCreate(BaseModel):
    exercise_id: UUID
    set_number: int = Field(..., description="Set ke-berapa (1, 2, 3, dst)", example=1)
    weight_kg: float = Field(..., description="Beban angkatan dalam kg", example=60.0)
    reps: int = Field(..., description="Jumlah repetisi gerakan", example=10)
    set_type: str = Field(default="normal", description="Tipe set: 'normal', 'warmup', 'dropset', 'failure'", example="normal")

# Data Structure
class WorkoutSetResponse(BaseModel):
    id: UUID
    session_id: UUID
    exercise_id: UUID
    set_number: int
    weight_kg: float
    reps: int
    set_type: str
    is_pr: bool  # Flag sakti buat memicu alert piala 🏆 di HP member!

    class Config:
        from_attributes = True


# Workout Session
class WorkoutSessionCreate(BaseModel):
    title: Optional[str] = Field(default="Sore Workout Session", description="Nama sesi latihan", example="Push Day Heavy")
    sets: List[WorkoutSetCreate] = Field(..., description="Array kumpulan set yang dieksekusi di sesi ini")

# Response
class WorkoutSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    duration_minutes: Optional[int]
    sets: List[WorkoutSetResponse] = []  

    class Config:
        from_attributes = True
        
class ExerciseCreate(BaseModel):
    """
    Schema for creating a new custom exercise.
    """
    name: str
    target_muscle: str

class ExerciseResponse(BaseModel):
    """
    Schema for exercise response.
    """
    id: str
    name: str
    target_muscle: str

    class Config:
        from_attributes = True # Penting untuk SQLAlchemy