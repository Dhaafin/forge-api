from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(db : Session = Depends(get_db), token : str = Depends(oauth2_scheme)) -> User:
    """
    Validates the incoming JWT access token and returns the current authenticated User entity.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate security credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # JWT Decode
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data_id = UUID(user_id)
    except (JWTError, ValueError):
        raise credentials_exception
        
    # Get User Data
    user = db.query(User).filter(User.id == token_data_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account profile.")
        
    return user