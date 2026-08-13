from pydantic import BaseModel
from typing import Optional, List
from enum import Enum
from datetime import datetime

class TelegramStatus(str, Enum):
    MEMBER = "MEMBER"
    ADMINISTRATOR = "ADMINISTRATOR"
    OWNER = "OWNER"
    RESTRICTED = "RESTRICTED"
    REQUEST_PENDING = "REQUEST_PENDING"
    NOT_JOINED = "NOT_JOINED"
    LEFT = "LEFT"
    BANNED = "BANNED"
    CHECK_ERROR = "CHECK_ERROR"
    # Legacy DB statuses mapped to display
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"
    ACTION_REQUIRED = "ACTION_REQUIRED"

class ApplicationResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"

class ChannelVerificationItem(BaseModel):
    id: int
    title: str
    label: str
    invite_link: Optional[str]
    verification_method: str
    telegram_status: str  # TelegramStatus value
    application_result: str  # ApplicationResult value

class VerificationCheckResponse(BaseModel):
    success: bool
    overall: str  # ApplicationResult
    passed_count: int
    total_required: int
    all_passed: bool
    requirements: List[dict]
    new_credits: int
    message: str
    checked_at: str
