# Canonical error code registry for OkFansBot v2.0
# All API errors must use these codes. Never expose stack traces, SQL, or secrets.
from enum import Enum
from pydantic import BaseModel

class ErrorCode(str, Enum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    RATE_LIMITED = "RATE_LIMITED"
    NETWORK_ERROR = "NETWORK_ERROR"
    TELEGRAM_UNAVAILABLE = "TELEGRAM_UNAVAILABLE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    SERVER_ERROR = "SERVER_ERROR"
    ACCOUNT_BANNED = "ACCOUNT_BANNED"

class ApiError(BaseModel):
    error: ErrorCode
    message: str  # Human-readable, safe to display in UI
