from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserUpdate, UserResponse

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user profile details.
    """
    return current_user


@router.patch("/me", response_model=UserResponse)
def update_user_profile(
    obj_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update profile fields (name, preferred unit, physical metrics, goals, etc.) for the current user.
    """
    update_data = obj_in.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
        
    db.commit()
    db.refresh(current_user)
    return current_user
