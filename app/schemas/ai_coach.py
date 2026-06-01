from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

common_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)

class AICoachRequest(BaseModel):
    session_id: UUID = Field(..., description="The UUID of the workout session to analyze")

class AICoachResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_id: UUID
    prompt: str
    response: str
    model_used: str
    tokens_prompt: Optional[int] = None
    tokens_completion: Optional[int] = None
    created_at: datetime

    model_config = common_config
