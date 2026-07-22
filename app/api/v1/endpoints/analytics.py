from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from collections import defaultdict
from uuid import UUID

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.workout_session import WorkoutSession
from app.models.workout_set import WorkoutSet
from app.models.exercise import Exercise
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    VolumeHistoryEntry,
    ExerciseAnalyticsResponse,
    ExerciseProgressEntry
)

router = APIRouter()

@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(
    range: str = Query("30d", enum=["7d", "30d", "90d", "1y", "all"]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Compute daily workout volume trend, total active workouts, total lift time, 
    and target muscle group volume distribution dynamically. Matches the user's preferred unit.
    """
    start_date = None
    if range != "all":
        now = datetime.utcnow()
        if range == "7d":
            start_date = now - timedelta(days=7)
        elif range == "30d":
            start_date = now - timedelta(days=30)
        elif range == "90d":
            start_date = now - timedelta(days=90)
        elif range == "1y":
            start_date = now - timedelta(days=365)
            
    query = db.query(WorkoutSession).filter(WorkoutSession.user_id == current_user.id)
    if start_date:
        query = query.filter(WorkoutSession.start_time >= start_date)
        
    sessions = query.order_by(WorkoutSession.start_time.asc()).all()
    
    unit = "lbs" if current_user.preferred_unit == "imperial" else "kg"
    conversion_factor = 2.20462 if current_user.preferred_unit == "imperial" else 1.0
    
    total_workouts = len(sessions)
    total_duration_minutes = sum(ws.duration_minutes or 0 for ws in sessions)
    
    total_volume = 0.0
    muscle_distribution = defaultdict(int)
    volume_by_date = defaultdict(float)
    
    for ws in sessions:
        date_str = ws.start_time.strftime("%Y-%m-%d")
        daily_session_vol = 0.0
        
        for s in ws.sets:
            vol = (s.weight_kg * s.reps) * conversion_factor
            daily_session_vol += vol
            
            if s.exercise:
                muscle_distribution[s.exercise.target_muscle] += 1
                
        total_volume += daily_session_vol
        volume_by_date[date_str] += daily_session_vol
        
    volume_history = [
        VolumeHistoryEntry(date=d, volume=round(v, 2))
        for d, v in sorted(volume_by_date.items())
    ]
    
    return AnalyticsOverviewResponse(
        total_volume=round(total_volume, 2),
        total_workouts=total_workouts,
        total_duration_minutes=total_duration_minutes,
        muscle_distribution=dict(muscle_distribution),
        volume_history=volume_history,
        unit=unit
    )


@router.get("/exercise/{exercise_id}", response_model=ExerciseAnalyticsResponse)
def get_exercise_analytics(
    exercise_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get progression details for a specific exercise over time. 
    Computes max weight and estimated 1RM (One Rep Max) via the Epley formula.
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not exercise:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exercise not found."
        )
    
    sets = db.query(WorkoutSet).join(WorkoutSession).filter(
        WorkoutSession.user_id == current_user.id,
        WorkoutSet.exercise_id == exercise_id
    ).order_by(WorkoutSession.start_time.asc()).all()
    
    if not sets:
        return ExerciseAnalyticsResponse(
            exercise_id=exercise_id,
            exercise_name=exercise.name,
            max_weight=0.0,
            max_estimated_1rm=0.0,
            history=[],
            unit="lbs" if current_user.preferred_unit == "imperial" else "kg"
        )
        
    unit = "lbs" if current_user.preferred_unit == "imperial" else "kg"
    conversion_factor = 2.20462 if current_user.preferred_unit == "imperial" else 1.0
    
    progress_by_date = {}
    for s in sets:
        session_date = s.session.start_time.strftime("%Y-%m-%d")
        
        weight = s.weight_kg * conversion_factor
        
        # Epley Formula for 1RM: weight * (1 + reps / 30) for reps > 1
        if s.reps > 1:
            est_1rm = weight * (1.0 + s.reps / 30.0)
        else:
            est_1rm = weight
            
        if session_date not in progress_by_date:
            progress_by_date[session_date] = {
                "max_weight": weight,
                "max_estimated_1rm": est_1rm
            }
        else:
            progress_by_date[session_date]["max_weight"] = max(progress_by_date[session_date]["max_weight"], weight)
            progress_by_date[session_date]["max_estimated_1rm"] = max(progress_by_date[session_date]["max_estimated_1rm"], est_1rm)
            
    history_entries = []
    max_weight_overall = 0.0
    max_1rm_overall = 0.0
    
    for d in sorted(progress_by_date.keys()):
        data = progress_by_date[d]
        max_w = round(data["max_weight"], 2)
        max_1r = round(data["max_estimated_1rm"], 2)
        
        max_weight_overall = max(max_weight_overall, max_w)
        max_1rm_overall = max(max_1rm_overall, max_1r)
        
        history_entries.append(
            ExerciseProgressEntry(
                date=d,
                max_weight=max_w,
                estimated_1rm=max_1r
            )
        )
        
    return ExerciseAnalyticsResponse(
        exercise_id=exercise_id,
        exercise_name=exercise.name,
        max_weight=max_weight_overall,
        max_estimated_1rm=max_1rm_overall,
        history=history_entries,
        unit=unit
    )
