from pydantic import BaseModel
from typing import List

class DailyClaimResponse(BaseModel):
    success: bool
    credits_earned: int
    streak: int
    new_balance: int
    message: str

class RedeemResponse(BaseModel):
    success: bool
    bundle_size: int
    new_credits: int
    message: str
