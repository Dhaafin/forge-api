# app/api/v1/endpoints/workouts.py
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.exercise import Exercise
from app.models.workout_session import WorkoutSession
from app.models.workout_set import WorkoutSet
from app.schemas.workout import WorkoutSessionCreate, WorkoutSessionResponse, ExerciseResponse

router = APIRouter()

@router.get("/exercises", response_model=List[ExerciseResponse])
def get_exercise_library(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch the list of all available structural exercises for the exercise picker menu.
    """
    return db.query(Exercise).order_by(Exercise.target_muscle).all()


@router.post("/session", response_model=WorkoutSessionResponse, status_code=status.HTTP_201_CREATED)
def record_workout_session(obj_in: WorkoutSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Log a completed workout session with its comprehensive array of sets.
    Implements real-time Personal Record (PR) detection per exercise.
    """
    # 1. Initialize and save the parent Workout Session
    db_session = WorkoutSession(
        user_id=current_user.id,
        title=obj_in.title,
        start_time=datetime.utcnow(),
        end_time=datetime.utcnow(),
        duration_minutes=60 # Default static estimation for MVP baseline
    )
    db.add(db_session)
    db.flush() # Secure the db_session.id before adding children sets

    saved_sets = []

    # 2. Iterate and process each incoming structural set item
    for set_data in obj_in.sets:
        # Verify if the chosen exercise profile exists
        exercise_exists = db.query(Exercise).filter(Exercise.id == set_data.exercise_id).first()
        if not exercise_exists:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Exercise parameter with ID {set_data.exercise_id} not found."
            )

        # 🚀 THE PR DETECTION ENGINE LOGIC
        # Query the highest weight ever lifted by THIS user for THIS specific exercise
        max_previous_weight = db.query(func.max(WorkoutSet.weight_kg)).\
            join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
            filter(WorkoutSession.user_id == current_user.id).\
            filter(WorkoutSet.exercise_id == set_data.exercise_id).scalar()

        # Determine if the current lift sets a new milestone
        is_personal_record = False
        if max_previous_weight is None or set_data.weight_kg > max_previous_weight:
            is_personal_record = True

        # 3. Instantiate and persist the child WorkoutSet record
        db_set = WorkoutSet(
            session_id=db_session.id,
            exercise_id=set_data.exercise_id,
            set_number=set_data.set_number,
            weight_kg=set_data.weight_kg,
            reps=set_data.reps,
            set_type=set_data.set_type,
            is_pr=is_personal_record
        )
        db.add(db_set)
        saved_sets.append(db_set)

    db.commit()
    
    # Refresh to safely serialize nested SQLAlchemy objects back to Pydantic
    db.refresh(db_session)
    return db_session