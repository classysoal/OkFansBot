from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MiniAppAuthRequest(BaseModel):
    initData: str

class UserSummary(BaseModel):
    user_id: int
    username: Optional[str]
    first_name: str
    credits: int
    vip_level: int
    starter_completed: bool

class SessionResponse(BaseModel):
    success: bool
    session_token: str
    expires_at: str
    account_created: bool
    user: dict  # UserSummary dict
