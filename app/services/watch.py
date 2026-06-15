import re
import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.schemas.watch import WatchSessionCreate, WatchSessionUpdate

def parse_watch_time(date_str: str, time_str: str, tz_str: str) -> datetime:
    """Parses date and time strings into a UTC datetime object."""
    date_parts = re.split(r"[\.,]", date_str)
    time_match = re.match(r"(\d{1,2}):(\d{2})\s*(AM|PM)", time_str.upper())
    if not time_match:
        raise ValueError("Invalid time format. Expected e.g. 09:00 PM")
        
    hour = int(time_match.group(1))
    minute = int(time_match.group(2))
    ampm = time_match.group(3)
    if ampm == "PM" and hour < 12: hour += 12
    elif ampm == "AM" and hour == 12: hour = 0
        
    local_dt = datetime(int(date_parts[2]), int(date_parts[0]), int(date_parts[1]), hour, minute, tzinfo=zoneinfo.ZoneInfo(tz_str))
    return local_dt.astimezone(timezone.utc)

class WatchService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.watch_sessions = self.db["watch_sessions"]
        self.users = self.db["users"]

    async def _get_couple_ids(self, user_id: str) -> List[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return sorted([user_id, user["partner"]["user_id"]])
        return [user_id]

    async def create_session(self, user_id: str, payload: WatchSessionCreate) -> Dict[str, Any]:
        couple_ids = await self._get_couple_ids(user_id)
        if len(couple_ids) < 2:
            raise ValueError("Alignment with partner required to schedule watch sessions.")

        utc_ts = parse_watch_time(payload.date, payload.time, payload.timezone)
        
        new_doc = payload.model_dump()
        new_doc["user_ids"] = couple_ids
        new_doc["utc_timestamp"] = utc_ts
        new_doc["created_at"] = datetime.now(timezone.utc)
        new_doc["updated_at"] = datetime.now(timezone.utc)
        
        # Initial sync states
        new_doc["is_accepted_user_1"] = False
        new_doc["is_accepted_user_2"] = False
        new_doc["is_ready_user_1"] = False
        new_doc["is_ready_user_2"] = False
        new_doc["notification_fired"] = False
        new_doc["is_playing"] = False
        new_doc["play_triggered_at"] = None

        # Initiator auto-accepts
        idx = couple_ids.index(user_id)
        new_doc[f"is_accepted_user_{idx+1}"] = True

        result = await self.watch_sessions.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_session(new_doc, user_id)

    async def accept_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.watch_sessions.find_one({"_id": ObjectId(session_id), "user_ids": user_id})
        if not doc:
            raise ValueError("Session not found.")

        idx = doc["user_ids"].index(user_id)
        field = f"is_accepted_user_{idx+1}"
        
        result = await self.watch_sessions.find_one_and_update(
            {"_id": ObjectId(session_id)},
            {"$set": {field: True, "updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_session(result, user_id)

    async def get_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        couple_ids = await self._get_couple_ids(user_id)
        cursor = self.watch_sessions.find({"user_ids": couple_ids}).sort("utc_timestamp", 1)
        docs = await cursor.to_list(length=None)
        return [await self._map_session(d, user_id) for d in docs]

    async def get_session(self, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        doc = await self.watch_sessions.find_one({"_id": ObjectId(session_id), "user_ids": user_id})
        if doc:
            return await self._map_session(doc, user_id)
        return None

    async def update_session(self, session_id: str, user_id: str, payload: WatchSessionUpdate) -> Optional[Dict[str, Any]]:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return await self.get_session(session_id, user_id)

        existing = await self.watch_sessions.find_one({"_id": ObjectId(session_id), "user_ids": user_id})
        if not existing:
            return None

        if any(k in updates for k in ["date", "time", "timezone"]):
            new_date = updates.get("date", existing["date"])
            new_time = updates.get("time", existing["time"])
            new_tz = updates.get("timezone", existing["timezone"])
            updates["utc_timestamp"] = parse_watch_time(new_date, new_time, new_tz)

        updates["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.watch_sessions.find_one_and_update(
            {"_id": ObjectId(session_id), "user_ids": user_id},
            {"$set": updates},
            return_document=True
        )
        if result:
            return await self._map_session(result, user_id)
        return None

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        result = await self.watch_sessions.delete_one({"_id": ObjectId(session_id), "user_ids": user_id})
        return result.deleted_count > 0

    async def set_ready(self, session_id: str, user_id: str, is_ready: bool) -> Dict[str, Any]:
        doc = await self.watch_sessions.find_one({"_id": ObjectId(session_id), "user_ids": user_id})
        if not doc:
            raise ValueError("Session not found.")

        if not doc["is_accepted_user_1"] or not doc["is_accepted_user_2"]:
            raise ValueError("Both partners must accept the session before marking ready.")

        idx = doc["user_ids"].index(user_id)
        field = f"is_ready_user_{idx+1}"
        
        updates = {field: is_ready, "updated_at": datetime.now(timezone.utc)}
        
        # If both are ready, fire notification
        partner_idx = 1 - idx
        if is_ready and doc[f"is_ready_user_{partner_idx+1}"]:
            updates["notification_fired"] = True

        result = await self.watch_sessions.find_one_and_update(
            {"_id": ObjectId(session_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_session(result, user_id)

    async def trigger_play(self, session_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.watch_sessions.find_one({"_id": ObjectId(session_id), "user_ids": user_id})
        if not doc:
            raise ValueError("Session not found.")
            
        if not doc["is_ready_user_1"] or not doc["is_ready_user_2"]:
            raise ValueError("Both partners must be ready before playing.")

        now = datetime.now(timezone.utc)
        result = await self.watch_sessions.find_one_and_update(
            {"_id": ObjectId(session_id)},
            {"$set": {
                "is_playing": True, 
                "play_triggered_at": now,
                "updated_at": now
            }},
            return_document=True
        )
        return await self._map_session(result, user_id)

    async def _map_session(self, d: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        
        idx = d["user_ids"].index(user_id)
        partner_idx = 1 - idx
        
        d["is_accepted_user"] = d[f"is_accepted_user_{idx+1}"]
        d["is_accepted_partner"] = d[f"is_accepted_user_{partner_idx+1}"]
        
        d["is_ready_user"] = d[f"is_ready_user_{idx+1}"]
        d["is_ready_partner"] = d[f"is_ready_user_{partner_idx+1}"]
        
        # Dynamic Notification Logic:
        # 1. Both ready (Manual trigger)
        # 2. Scheduled time reached AND both accepted (Auto trigger)
        now = datetime.now(timezone.utc)
        is_both_accepted = d[f"is_accepted_user_{idx+1}"] and d[f"is_accepted_user_{partner_idx+1}"]
        time_reached = now >= d["utc_timestamp"].replace(tzinfo=timezone.utc) if d["utc_timestamp"].tzinfo is None else now >= d["utc_timestamp"]
        
        if not d.get("notification_fired"):
            if is_both_accepted and time_reached:
                d["notification_fired"] = True
        
        # Cleanup internal fields
        if "_id" in d: del d["_id"]
        if "is_accepted_user_1" in d: del d["is_accepted_user_1"]
        if "is_accepted_user_2" in d: del d["is_accepted_user_2"]
        if "is_ready_user_1" in d: del d["is_ready_user_1"]
        if "is_ready_user_2" in d: del d["is_ready_user_2"]
        
        return d

watch_service = WatchService()
