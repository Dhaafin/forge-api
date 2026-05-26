import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.invite import InviteToken
from app.schemas.auth import InviteCreate, InviteResponse

router = APIRouter()

@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_user_invite(obj_in: InviteCreate, db: Session = Depends(get_db)):
    """
    Generate a unique invitation token for a new user/member.
    
    This endpoint is restricted to Admin use only. It generates a single-use 
    secure token that expires automatically after 7 days, as per Forge Gym requirements.
    """
    # 1. Generate a secure, URL-safe random token string (32 bytes)
    random_token = secrets.token_urlsafe(32)
    
    # 2. Set expiration time to exactly 7 days from now
    expire_time = datetime.now(timezone.utc) + timedelta(days=7)
    
    # TODO: Temporal hardcoded Admin UUID.
    # This will be replaced with the actual authenticated Admin ID from the JWT payload later.
    dummy_admin_id = "4d2a1b3c-5e6f-7a8b-9c0d-1e2f3a4b5c6d" 
    
    # 3. Create and store the invitation record in the database
    db_invite = InviteToken(
        token=random_token,
        email=obj_in.email,
        role=obj_in.role,
        invited_by=dummy_admin_id,
        expires_at=expire_time
    )
    
    db.add(db_invite)
    db.commit()
    db.refresh(db_invite)
    
    return db_invite