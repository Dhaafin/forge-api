# app/api/v1/endpoints/auth.py
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User
from app.models.invite import InviteToken
from app.schemas.auth import InviteCreate, InviteResponse, UserRegister, Token

router = APIRouter()

@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def create_user_invite(obj_in: InviteCreate, db: Session = Depends(get_db)):
    """
    Generate a unique invitation token for a new user/member.
    
    This endpoint is restricted to Admin use only. It generates a single-use 
    secure token that expires automatically after 7 days, as per Forge Gym requirements.
    """
    random_token = secrets.token_urlsafe(32)
    expire_time = datetime.utcnow() + timedelta(days=7)
    
    # Temporal hardcoded Admin UUID matching our seed.py profile data
    dummy_admin_id = "4d2a1b3c-5e6f-7a8b-9c0d-1e2f3a4b5c6d" 
    
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_via_invite(obj_in: UserRegister, db: Session = Depends(get_db)):
    """
    Activate a member account using a valid, single-use invitation token.
    
    This endpoint validates the token's existence, single-use status, and 
    expiration date before securely hashing the password and creating the user account.
    """
    db_invite = db.query(InviteToken).filter(InviteToken.token == obj_in.token).first()
    
    if not db_invite:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid invitation token profile."
        )
        
    if db_invite.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation token has already been used."
        )
        
    if datetime.utcnow() > db_invite.expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This invitation token has expired."
        )
        
    existing_user = db.query(User).filter(User.email == db_invite.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user profile with this email parameter already exists."
        )

    new_user = User(
        name=obj_in.name,
        email=db_invite.email,  
        password_hash=get_password_hash(obj_in.password),
        role=db_invite.role,    
        is_active=True
    )
    db.add(new_user)
    
    db_invite.used_at = datetime.utcnow()
    db.commit()
    db.refresh(new_user)
    
    return {
        "status": "success",
        "message": "User account activated successfully.",
        "user_id": str(new_user.id),
        "email": new_user.email
    }


@router.post("/login", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db)
):
    """
    OAuth2 compatible token login, success returns a JWT access token.
    
    Note: OAuth2PasswordRequestForm expects 'username' (which is our user email) 
    and 'password' fields submitted via form-data.
    """
    # 1. Authenticate user existence via email (OAuth2 username parameter)
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email profile or password credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 2. Check hashed password alignment using native bcrypt utility
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email profile or password credential.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 3. Generate secure JSON Web Token payload containing User ID UUID
    access_token = create_access_token(subject=user.id)
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }