from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.core.config import settings

class InteractionService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.interactions = self.db["partner_interactions"]
        self.users = self.db["users"]

    async def init_indexes(self):
        # TTL Index to clear data. Since we want a "midnight" reset feel, 
        # we can use a TTL on a "reset_at" field or just expire documents after 24 hours.
        # However, for a strict midnight reset, we'll store a "date" string and query by it,
        # and let the TTL clean up old days.
        await self.interactions.create_index("created_at", expireAfterSeconds=172800) # Keep for 2 days just in case

    async def _get_couple_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("is_aligned") or not user.get("partner"):
            return None
        return {
            "user_id": user_id,
            "user_name": user.get("name", "User"),
            "partner_id": user["partner"]["user_id"],
            "partner_name": user["partner"].get("name", "Partner")
        }

    def _get_today_str(self) -> str:
        # Midnight reset usually implies the user's local day, 
        # but for backend we'll use UTC date.
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async def increment_count(self, user_id: str) -> bool:
        info = await self._get_couple_info(user_id)
        if not info:
            return False

        today = self._get_today_str()
        # We track how many times the current user has "poked" the partner
        # But the requirement is "when partner hit that api, it will increase count +1, when user get this api response, it should contain partner name and count"
        # So we store it keyed by the recipient (the partner) or the sender?
        # "partner hit that api... user get this api response... contain partner name and count"
        # This means the count is "actions received from partner".
        
        # Key: recipient_id + date
        # Incrementing user_id's poke to partner_id
        await self.interactions.update_one(
            {
                "sender_id": user_id, 
                "recipient_id": info["partner_id"],
                "date": today
            },
            {
                "$inc": {"count": 1},
                "$set": {
                    "last_activity": datetime.now(timezone.utc),
                    "created_at": datetime.now(timezone.utc) # For TTL
                }
            },
            upsert=True
        )
        return True

    async def get_interaction_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        info = await self._get_couple_info(user_id)
        if not info:
            return None

        today = self._get_today_str()
        # The user wants to see how many times their partner has hit the api
        # So we look for documents where recipient_id == user_id
        doc = await self.interactions.find_one({
            "sender_id": info["partner_id"],
            "recipient_id": user_id,
            "date": today
        })

        return {
            "partner_name": info["partner_name"],
            "count": doc["count"] if doc else 0,
            "last_activity": doc["last_activity"] if doc else None
        }

interaction_service = InteractionService()
