from pydantic import BaseModel
from typing import List, Optional

class ActivityItem(BaseModel):
    icon: str
    title: str
    time: str
    status: str

class DashboardUser(BaseModel):
    user_id: int
    username: str
    first_name: str
    credits: int
    checkin_streak: int
    starter_completed: bool

class DashboardVip(BaseModel):
    level: int
    title: str
    badge: str
    bundle_size: int
    credit_cost: int
    invites_needed: int
    next_target: str
    progress_pct: int

class DashboardReferrals(BaseModel):
    ref_code: str
    ref_link: str
    verified_count: int
    qualified_count: int
    flash_bonus_credits: int
    standard_credits: int

class DashboardVerification(BaseModel):
    is_completed: bool
    completed_count: int
    total_required: int
    channels: List[dict]

class DashboardResponse(BaseModel):
    user: DashboardUser
    vip: DashboardVip
    referrals: DashboardReferrals
    verification: DashboardVerification
    recent_activity: List[dict]
    notifications_unread_count: int
