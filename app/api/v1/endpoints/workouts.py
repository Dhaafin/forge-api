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
from app.schemas.workout import WorkoutSessionCreate, WorkoutSessionResponse, ExerciseResponse, WorkoutSetResponse

router = APIRouter()

@router.get("/exercises", response_model=List[ExerciseResponse])
def get_exercise_library(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch the list of all available structural exercises for the exercise picker menu.
    """
    return db.query(Exercise).order_by(Exercise.target_muscle).all()

@router.put("/set/{set_id}", response_model=WorkoutSetResponse)
def update_workout_set_detail(
    set_id: str, 
    weight_kg: float = None, 
    reps: int = None, 
    set_type: str = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    [M6 Backend] Edit specific metrics (weight, reps, type) of an individual workout set row.
    """
    db_set = db.query(WorkoutSet).\
        join(WorkoutSession).\
        filter(WorkoutSet.id == set_id, WorkoutSession.user_id == current_user.id).\
        first()
        
    if not db_set:
        raise HTTPException(status_code=404, detail="Baris set latihan tidak ditemukan bos!")
        
    if weight_kg is not None:
        db_set.weight_kg = weight_kg
    if reps is not None:
        db_set.reps = reps
    if set_type is not None:
        db_set.set_type = set_type
        
    if weight_kg is not None:
        highest_past_weight = db.query(WorkoutSet.weight_kg).\
            join(WorkoutSession).\
            filter(WorkoutSession.user_id == current_user.id).\
            filter(WorkoutSet.exercise_id == db_set.exercise_id).\
            filter(WorkoutSet.id != db_set.id).\
            order_by(WorkoutSet.weight_kg.desc()).\
            first()
            
        db_set.is_pr = highest_past_weight is None or weight_kg > highest_past_weight[0]

    db.commit()
    db.refresh(db_set)
    return db_set

@router.delete("/set/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_single_workout_set(
    set_id: str, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    [M6 Backend] Permanently delete a single set row from a workout log session.
    """
    db_set = db.query(WorkoutSet).\
        join(WorkoutSession).\
        filter(WorkoutSet.id == set_id, WorkoutSession.user_id == current_user.id).\
        first()
        
    if not db_set:
        raise HTTPException(status_code=404, detail="Baris set tidak ditemukan atau bukan milikmu.")
        
    db.delete(db_set)
    db.commit()
    return None

@router.delete("/session/{session_id}", status_code=200)
def delete_workout_session(
    session_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Delete Workout Session
    """
    session = db.query(WorkoutSession).filter(
        WorkoutSession.id == session_id, 
        WorkoutSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Sesi latihan emang ga ada atau bukan punyamu.")
        
    # Hapus semua set yang terikat dengan session ini terlebih dahulu
    db.query(WorkoutSet).filter(WorkoutSet.session_id == session_id).delete()
    
    # Hapus sesi utamanya
    db.delete(session)
    db.commit()
    
    return {"status": "success", "message": f"Sesi latihan {session_id} berhasil di-wipe!"}

@router.delete("/exercises/{exercise_id}", status_code=200)
def delete_custom_exercise(
    exercise_id: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Remove Custom Exercises
    """
    exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    
    if not exercise:
        raise HTTPException(status_code=404, detail="Gerakan gym tidak ditemukan.")
        
    is_used = db.query(WorkoutSet).filter(WorkoutSet.exercise_id == exercise_id).first()
    
    if is_used:
        raise HTTPException(
            status_code=400, 
            detail="Gak bisa dihapus bos! Gerakan ini sudah masuk ke data history latihanmu. Hapus set latiitannya dulu."
        )
        
    db.delete(exercise)
    db.commit()
    
    return {"status": "success", "message": f"Gerakan '{exercise.name}' berhasil dihapus."}


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

    try:
        print(f"\n[ANALYTICS] 🧠 Scanning progressive overload status for Session: '{db_session.title}'")
        
        current_exercise_volumes = {}
        for s in saved_sets:
            if s.exercise_id not in current_exercise_volumes:
                current_exercise_volumes[s.exercise_id] = 0
            current_exercise_volumes[s.exercise_id] += (s.weight_kg * s.reps)

        for exercise_id, current_vol in current_exercise_volumes.items():
            ex_detail = db.query(Exercise).filter(Exercise.id == exercise_id).first()
            ex_name = ex_detail.name if ex_detail else "Unknown Exercise"

            last_set_with_same_exercise = db.query(WorkoutSet).\
                join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
                filter(WorkoutSession.user_id == current_user.id).\
                filter(WorkoutSession.id != db_session.id).\
                filter(WorkoutSet.exercise_id == exercise_id).\
                order_by(WorkoutSession.start_time.desc()).\
                first()

            if last_set_with_same_exercise:
                target_past_session_id = last_set_with_same_exercise.session_id
                
                past_sets = db.query(WorkoutSet).\
                    filter(WorkoutSet.session_id == target_past_session_id).\
                    filter(WorkoutSet.exercise_id == exercise_id).all()
                    
                past_vol = sum([s.weight_kg * s.reps for s in past_sets])

                if current_vol > past_vol:
                    diff = current_vol - past_vol
                    print(f"🔥 OVERLOAD DETECTED on [{ex_name}]: Volume naik +{diff} kg! (Hari ini: {current_vol}kg vs Terakhir: {past_vol}kg)")
                else:
                    print(f"ℹ️ [{ex_name}]: Latihan tercatat. Tidak ada overload ({current_vol}kg vs {past_vol}kg).")
            else:
                print(f"ℹ️ [{ex_name}]: Ini pertama kalinya user main gerakan ini. Belum ada data pembanding.")

        print("[ANALYTICS] ✅ Per-exercise progressive overload scan completed.\n")

    except Exception as analytic_error:
        print(f"⚠️ Analytic engine failed to calculate progressive overload: {str(analytic_error)}")
    return db_session