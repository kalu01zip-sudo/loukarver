import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.notification import (
    NotificationCreate, NotificationStatus, NotificationType
)

class NotificationService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.notifications_collection = self.db["notifications"]
        self.users = self.db["users"]

    async def init_indexes(self):
        await self.notifications_collection.create_index([("recipient_id", 1), ("status", 1)])
        await self.notifications_collection.create_index("scheduled_for")

    async def schedule_notification(self, sender_id: str, payload: NotificationCreate) -> Dict[str, Any]:
        new_doc = payload.model_dump()
        new_doc["sender_id"] = sender_id
        new_doc["status"] = NotificationStatus.SCHEDULED
        new_doc["created_at"] = datetime.now(timezone.utc)
        
        result = await self.notifications_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_notification(new_doc, payload.timezone)

    async def get_my_notifications(self, user_id: str, page: int = 1, size: int = 20, user_timezone: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        query = {"recipient_id": user_id}
        
        # Auto-mark delivered if scheduled time has passed
        now = datetime.now(timezone.utc)
        await self.notifications_collection.update_many(
            {"recipient_id": user_id, "status": NotificationStatus.SCHEDULED, "scheduled_for": {"$lte": now}},
            {"$set": {"status": NotificationStatus.DELIVERED, "delivered_at": now}}
        )

        skip = (page - 1) * size
        cursor = self.notifications_collection.find(query).sort("scheduled_for", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.notifications_collection.count_documents(query)

        return [await self._map_notification(d, user_timezone) for d in docs], total

    async def mark_as_seen(self, notification_id: str, user_id: str) -> bool:
        result = await self.notifications_collection.update_one(
            {"_id": ObjectId(notification_id), "recipient_id": user_id},
            {"$set": {"status": NotificationStatus.SEEN}}
        )
        return result.modified_count > 0

    async def _map_notification(self, d: Dict[str, Any], user_timezone: str) -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        if "_id" in d: del d["_id"]

        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        for field in ["scheduled_for", "created_at", "delivered_at"]:
            dt = d.get(field)
            if isinstance(dt, datetime):
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)

        return d

notification_service = NotificationService()
