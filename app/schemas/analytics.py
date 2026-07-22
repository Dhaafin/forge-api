from pydantic import BaseModel
from typing import List, Dict
from uuid import UUID

class VolumeHistoryEntry(BaseModel):
    date: str  # YYYY-MM-DD
    volume: float

class AnalyticsOverviewResponse(BaseModel):
    total_volume: float
    total_workouts: int
    total_duration_minutes: int
    muscle_distribution: Dict[str, int]
    volume_history: List[VolumeHistoryEntry]
    unit: str

class ExerciseProgressEntry(BaseModel):
    date: str  # YYYY-MM-DD
    max_weight: float
    estimated_1rm: float

class ExerciseAnalyticsResponse(BaseModel):
    exercise_id: UUID
    exercise_name: str
    max_weight: float
    max_estimated_1rm: float
    history: List[ExerciseProgressEntry]
    unit: str
