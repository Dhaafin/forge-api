from pydantic import BaseModel, EmailStr, Field

# Create New Invite Tokens
class InviteCreate(BaseModel):
    email: EmailStr
    role: str = Field(default="user", description="Between 'user' or 'admin'")
    
# Response Create New Invite Tokens
class InviteResponse(BaseModel):
    email: EmailStr
    token: str
    role: str
    
    class Config:
        from_attributes = True
        
# User Registration Schema When Invited
class UserRegister(BaseModel):
    token: str
    name: str
    password: str = Field(..., min_length=8, description="Password must have minimum of 8 characters")
    
# Normal Login    
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Login Response (JWT Token)    
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    