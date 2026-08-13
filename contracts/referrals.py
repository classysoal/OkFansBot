from pydantic import BaseModel
from typing import Optional

class ReferralsResponse(BaseModel):
    ref_code: str
    ref_link: str
    verified_count: int
    flash_bonus_active: bool
    flash_bonus_credits: int
    standard_credits: int

class SettingsData(BaseModel):
    notifications_enabled: bool = True
    language: str = "en"

class SettingsResponse(BaseModel):
    success: bool
    settings: SettingsData
