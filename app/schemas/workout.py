from enum import Enum
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# Menggunakan satu standar Config untuk semua class (Pydantic v2)
common_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class TargetMuscle(str, Enum):
    CHEST = "Chest"
    BACK = "Back"
    LEGS = "Legs"
    SHOULDERS = "Shoulders"
    ARMS = "Arms"
    CORE = "Core"
    CARDIO = "Cardio"
    FULL_BODY = "Full Body"

# 1. Exercise Schemas
class ExerciseResponse(BaseModel):
    id: UUID  # Gunakan UUID di sini
    name: str
    target_muscle: TargetMuscle

    model_config = common_config

class ExerciseCreate(BaseModel):
    name: str
    target_muscle: TargetMuscle

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

    @field_serializer('start_time', 'end_time')
    def serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        return dt.astimezone().strftime("%Y-%m-%dT%H:%M:%SZ")

# 4. AI Parsing Schemas
class WorkoutParseRequest(BaseModel):
    raw_text: str = Field(..., description="Raw text workout notes to parse", example="## 06-04-26 (Pull Day)\n- Lat Pulldowns 3 x 12 (30kg)")

class WorkoutParseSet(BaseModel):
    set_number: int
    weight_kg: float
    reps: int
    set_type: str = "normal"

class SuggestedExercise(BaseModel):
    id: UUID
    name: str
    target_muscle: TargetMuscle

    model_config = common_config

class WorkoutParseExerciseItem(BaseModel):
    raw_name: str
    matched: bool
    exercise_id: Optional[UUID] = None
    exercise_name: Optional[str] = None
    suggested_exercise: Optional[SuggestedExercise] = None
    inferred_target_muscle: Optional[TargetMuscle] = None
    sets: List[WorkoutParseSet] = []

    model_config = common_config

class WorkoutParseResponse(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    exercises: List[WorkoutParseExerciseItem] = []

    model_config = common_config