# app/api/v1/endpoints/workouts.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, date, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.exercise import Exercise
from app.models.workout_session import WorkoutSession
from app.models.workout_set import WorkoutSet
from app.schemas.workout import (
    WorkoutSessionCreate, WorkoutSessionResponse, ExerciseResponse, ExerciseCreate,
    WorkoutSetResponse, WorkoutParseRequest, WorkoutParseResponse, WorkoutParseExerciseItem,
    WorkoutParseSet, SuggestedExercise
)
from app.services.ai_service import parse_workout_notes_with_ai
import difflib

router = APIRouter()

# =====================================================================
# 📑 EXERCISE MANAGEMENT AREA (GLOBALLY AVAILABLE + USER CUSTOM)
# =====================================================================

@router.get("/exercises", response_model=List[ExerciseResponse])
def get_all_exercises(
    search: Optional[str] = Query(None, description="Search by exercise name or target muscle"),
    sort_by: str = Query("name", description="Field to sort by (name, target_muscle)"),
    order: str = Query("asc", description="Sort direction (asc, desc)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Limit pagination"),
    offset: Optional[int] = Query(0, ge=0, description="Offset pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Fetch the complete library of gym exercises available for the mobile workout tracker.
    Includes both default seeded exercises and custom user creations.
    """
    query = db.query(Exercise)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (Exercise.name.ilike(search_term)) | 
            (Exercise.target_muscle.ilike(search_term))
        )

    # Sort validation/mapping
    whitelisted_fields = {
        "name": Exercise.name,
        "target_muscle": Exercise.target_muscle
    }
    sort_column = whitelisted_fields.get(sort_by, Exercise.name)

    if order.lower() == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    return query.all()

@router.post("/exercises", response_model=ExerciseResponse, status_code=status.HTTP_201_CREATED)
def create_new_exercise(obj_in: ExerciseCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Allow users to dynamically add new exercise variants to the global library database.
    """
    existing_ex = db.query(Exercise).filter(Exercise.name == obj_in.name).first()
    if existing_ex:
        raise HTTPException(status_code=400, detail="An exercise with this exact name already exists.")
        
    db_exercise = Exercise(name=obj_in.name, target_muscle=obj_in.target_muscle)
    db.add(db_exercise)
    db.commit()
    db.refresh(db_exercise)
    return db_exercise

@router.put("/exercises/{exercise_id}", response_model=ExerciseResponse)
def update_exercise_metadata(exercise_id: str, name: str, target_muscle: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Modify metadata specifications (name or target muscle) of a specific gym movement entry.
    """
    db_exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not db_exercise:
        raise HTTPException(status_code=404, detail="Exercise profile not found.")
        
    db_exercise.name = name
    db_exercise.target_muscle = target_muscle
    db.commit()
    db.refresh(db_exercise)
    return db_exercise

@router.delete("/exercises/{exercise_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_exercise_record(exercise_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Safely remove an exercise option. Protected by Restrict Constraint to prevent breaking historical workout logs.
    """
    db_exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
    if not db_exercise:
        raise HTTPException(status_code=404, detail="Exercise profile not found.")
        
    # INTEGRITY PROTECTION: Check if this exercise ID is already tied to past workout sets
    is_used = db.query(WorkoutSet).filter(WorkoutSet.exercise_id == exercise_id).first()
    if is_used:
        raise HTTPException(
            status_code=400, 
            detail="Cannot delete this exercise. It is already linked to historical workout sets. Remove the sets first."
        )
        
    db.delete(db_exercise)
    db.commit()
    return None

# =====================================================================
# 🏋️‍♂️ WORKOUT SESSION REGISTRATION & PR ENGINE
# =====================================================================

@router.get("/session/history", response_model=List[WorkoutSessionResponse])
def get_workout_history(
    search: Optional[str] = Query(None, description="Search in session title"),
    start_date: Optional[date] = Query(None, description="Filter sessions starting on or after this date"),
    end_date: Optional[date] = Query(None, description="Filter sessions starting on or before this date"),
    time_window: Optional[str] = Query(None, description="Quick time presets: '7d', '30d', '90d', 'ytd'"),
    sort_by: str = Query("start_time", description="Field to sort by (start_time, duration_minutes, title)"),
    order: str = Query("desc", description="Sort direction (asc, desc)"),
    limit: Optional[int] = Query(20, ge=1, le=100, description="Limit pagination"),
    offset: Optional[int] = Query(0, ge=0, description="Offset pagination"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieve all historical training logs belonging exclusively to the authenticated user.
    Supports searching by title, sorting, date-range/window filtering, and pagination.
    """
    query = db.query(WorkoutSession).filter(WorkoutSession.user_id == current_user.id)

    # Search (title only)
    if search:
        query = query.filter(WorkoutSession.title.ilike(f"%{search}%"))

    # Explicit boundaries
    if start_date:
        query = query.filter(WorkoutSession.start_time >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(WorkoutSession.start_time <= datetime.combine(end_date, datetime.max.time()))

    # Time Window presets (only applies if start_date/end_date are not provided)
    if time_window and not (start_date or end_date):
        now = datetime.utcnow()
        if time_window == "7d":
            query = query.filter(WorkoutSession.start_time >= now - timedelta(days=7))
        elif time_window == "30d":
            query = query.filter(WorkoutSession.start_time >= now - timedelta(days=30))
        elif time_window == "90d":
            query = query.filter(WorkoutSession.start_time >= now - timedelta(days=90))
        elif time_window == "ytd":
            query = query.filter(WorkoutSession.start_time >= datetime(now.year, 1, 1))

    # Sort validation/mapping
    whitelisted_fields = {
        "start_time": WorkoutSession.start_time,
        "duration_minutes": WorkoutSession.duration_minutes,
        "title": WorkoutSession.title
    }
    sort_column = whitelisted_fields.get(sort_by, WorkoutSession.start_time)

    if order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    if limit is not None:
        query = query.limit(limit)
    if offset is not None:
        query = query.offset(offset)

    return query.all()

@router.post("/session", response_model=WorkoutSessionResponse, status_code=status.HTTP_201_CREATED)
def record_workout_session(obj_in: WorkoutSessionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Commit a new active training log. Auto-evaluates historical sets to flag Personal Records (PR)
    and processes progressive overload analytics in the background.
    """
    # 1. Validate that all exercise IDs exist in the database
    exercise_ids = {s.exercise_id for s in obj_in.sets}
    if exercise_ids:
        existing_exercises = db.query(Exercise.id).filter(Exercise.id.in_(exercise_ids)).all()
        existing_ids = {e.id for e in existing_exercises}
        missing_ids = exercise_ids - existing_ids
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Exercise(s) not found: {', '.join(str(m) for m in missing_ids)}"
            )

    # 2. Initialize the parent session entity (handling retroactive start/end/duration)
    session_start = obj_in.start_time or datetime.utcnow()
    if obj_in.end_time:
        session_end = obj_in.end_time
        calc_duration = int((session_end - session_start).total_seconds() / 60)
        duration = obj_in.duration_minutes or max(0, calc_duration)
    else:
        duration = obj_in.duration_minutes or 0
        session_end = session_start + timedelta(minutes=duration)

    db_session = WorkoutSession(
        user_id=current_user.id,
        title=obj_in.title,
        start_time=session_start,
        end_time=session_end,
        duration_minutes=duration
    )
    db.add(db_session)
    db.flush()  # Generate UUID/ID for db_session without committing the transaction

    # 3. Iterate through incoming sets and evaluate Personal Records (PR)
    for s in obj_in.sets:
        highest_past_weight = db.query(WorkoutSet.weight_kg).\
            join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
            filter(WorkoutSession.user_id == current_user.id).\
            filter(WorkoutSet.exercise_id == s.exercise_id).\
            filter(WorkoutSession.id != db_session.id).\
            order_by(WorkoutSet.weight_kg.desc()).\
            first()

        is_new_pr = False
        if highest_past_weight is None or s.weight_kg > highest_past_weight[0]:
            is_new_pr = True

        db_set = WorkoutSet(
            session_id=db_session.id,
            exercise_id=s.exercise_id,
            set_number=s.set_number,
            weight_kg=s.weight_kg,
            reps=s.reps,
            set_type=s.set_type,
            is_pr=is_new_pr
        )
        db.add(db_set)

    db.commit()
    db.refresh(db_session)

    # 3. BACKGROUND AI: Granular Progressive Overload Detector (M5)
    try:
        current_volumes = {}
        for s in db.query(WorkoutSet).filter(WorkoutSet.session_id == db_session.id).all():
            if s.exercise_id not in current_volumes:
                current_volumes[s.exercise_id] = 0
            current_volumes[s.exercise_id] += (s.weight_kg * s.reps)

        for exercise_id, current_vol in current_volumes.items():
            last_past_set = db.query(WorkoutSet).\
                join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
                filter(WorkoutSession.user_id == current_user.id).\
                filter(WorkoutSession.id != db_session.id).\
                filter(WorkoutSet.exercise_id == exercise_id).\
                order_by(WorkoutSession.start_time.desc()).\
                first()

            if last_past_set:
                past_sets = db.query(WorkoutSet).\
                    filter(WorkoutSet.session_id == last_past_set.session_id).\
                    filter(WorkoutSet.exercise_id == exercise_id).all()
                past_vol = sum([s.weight_kg * s.reps for s in past_sets])

                if current_vol > past_vol:
                    print(f"🔥 OVERLOAD DETECTED: Volume increased for exercise ID {exercise_id} ({current_vol}kg vs {past_vol}kg)")
    except Exception as e:
        print(f"⚠️ Analytics Engine Error: {str(e)}")

    return db_session

@router.put("/session/{session_id}", response_model=WorkoutSessionResponse)
def update_workout_session(session_id: str, title: str = None, duration_minutes: int = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Allow dynamic updates to session titles or training length logs from the mobile screen.
    """
    db_session = db.query(WorkoutSession).filter(WorkoutSession.id == session_id, WorkoutSession.user_id == current_user.id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Workout log entry not found.")
        
    if title is not None:
        db_session.title = title
    if duration_minutes is not None:
        db_session.duration_minutes = duration_minutes
        
    db.commit()
    db.refresh(db_session)
    return db_session

@router.delete("/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout_session(session_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Cascade-delete an entire faulty log entry along with its child performance metrics parameters.
    """
    db_session = db.query(WorkoutSession).filter(WorkoutSession.id == session_id, WorkoutSession.user_id == current_user.id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Workout log entry not found.")
        
    db.delete(db_session)
    db.commit()
    return None

# =====================================================================
# ⚙️ SUB-CRUD: INDIVIDUAL SET MANIPULATION
# =====================================================================

@router.put("/set/{set_id}", response_model=WorkoutSetResponse)
def update_workout_set_detail(set_id: str, weight_kg: float = None, reps: int = None, set_type: str = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Modify specific metrics (weight, reps, type) of an individual workout set row.
    Automatically recalculates the Personal Record (PR) flag if weight changes.
    """
    db_set = db.query(WorkoutSet).\
        join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
        filter(WorkoutSet.id == set_id, WorkoutSession.user_id == current_user.id).\
        first()
        
    if not db_set:
        raise HTTPException(status_code=404, detail="Set row not found or unauthorized.")
        
    if weight_kg is not None:
        db_set.weight_kg = weight_kg
    if reps is not None:
        db_set.reps = reps
    if set_type is not None:
        db_set.set_type = set_type
        
    # Dynamically re-evaluate PR flag upon weight alteration
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
def delete_single_workout_set(set_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Permanently delete a single set row from a workout log session.
    """
    db_set = db.query(WorkoutSet).\
        join(WorkoutSession, WorkoutSet.session_id == WorkoutSession.id).\
        filter(WorkoutSet.id == set_id, WorkoutSession.user_id == current_user.id).\
        first()
        
    if not db_set:
        raise HTTPException(status_code=404, detail="Set row not found or unauthorized.")
        
    db.delete(db_set)
    db.commit()
    return None

# =====================================================================
# 🔔 DEVICE TOKEN REGISTRATION (M5)
# =====================================================================

class PushTokenPayload(BaseModel):
    token: str

@router.post("/push-token", status_code=status.HTTP_200_OK)
def register_device_push_token(payload: PushTokenPayload, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Receive and store the unique Expo Notification Token from the user's mobile device 
    for the proactive reminder engine.
    """
    current_user.expo_push_token = payload.token
    db.commit()
    return {"status": "success", "message": "Device push token successfully linked to your account."}


@router.post("/session/parse-notes", response_model=WorkoutParseResponse)
async def parse_workout_notes_endpoint(
    payload: WorkoutParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Parse unstructured workout notes using AI and perform fuzzy match logic to associate
    exercise names with database entries.
    """
    parsed_json = await parse_workout_notes_with_ai(payload.raw_text)
    
    db_exercises = db.query(Exercise).all()
    exercise_name_map = {e.name.lower().strip(): e for e in db_exercises}
    exercise_names = list(exercise_name_map.keys())

    response_exercises = []

    for item in parsed_json.get("exercises", []):
        raw_name = item.get("raw_name", "").strip()
        raw_name_lower = raw_name.lower()
        
        matched = False
        exercise_id = None
        exercise_name = None
        suggested_exercise = None

        if raw_name_lower in exercise_name_map:
            matched = True
            db_ex = exercise_name_map[raw_name_lower]
            exercise_id = db_ex.id
            exercise_name = db_ex.name
        else:
            matches = difflib.get_close_matches(raw_name_lower, exercise_names, n=1, cutoff=0.6)
            if matches:
                db_ex = exercise_name_map[matches[0]]
                suggested_exercise = SuggestedExercise(
                    id=db_ex.id,
                    name=db_ex.name,
                    target_muscle=db_ex.target_muscle
                )

        sets_list = []
        for set_data in item.get("sets", []):
            sets_list.append(
                WorkoutParseSet(
                    set_number=set_data.get("set_number", 1),
                    weight_kg=float(set_data.get("weight_kg", 0.0)),
                    reps=int(set_data.get("reps", 0)),
                    set_type=set_data.get("set_type", "normal")
                )
            )

        response_exercises.append(
            WorkoutParseExerciseItem(
                raw_name=raw_name,
                matched=matched,
                exercise_id=exercise_id,
                exercise_name=exercise_name,
                suggested_exercise=suggested_exercise,
                inferred_target_muscle=item.get("inferred_target_muscle"),
                sets=sets_list
            )
        )

    return WorkoutParseResponse(
        title=parsed_json.get("title"),
        date=parsed_json.get("date"),
        exercises=response_exercises
    )