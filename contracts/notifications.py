from pydantic import BaseModel
from typing import List
from datetime import datetime

class NotificationItem(BaseModel):
    id: int
    type: str  # 'reward', 'verification', 'referral', 'system'
    title: str
    body: str
    read: bool
    created_at: str

class NotificationsResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int

class MarkReadRequest(BaseModel):
    notification_ids: List[int]  # empty list = mark all read
