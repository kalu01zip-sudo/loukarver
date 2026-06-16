import re
import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.schemas.dates import (
    DateCreate, DateUpdate, DateStatus, DateRespond, DateReviewCreate
)

def parse_date_time(date_str: str, time_str: str, tz_str: str) -> datetime:
    """Parses date and time strings into a UTC datetime object."""
    # Handle both . and , as separators
    date_parts = re.split(r"[\.,]", date_str)
    if len(date_parts) != 3:
        raise ValueError("Invalid date format. Expected e.g. 12.25.2023")
        
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

class DateService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.dates_collection = self.db["dates"]
        self.users = self.db["users"]

    async def init_indexes(self):
        await self.dates_collection.create_index([("creator_id", 1), ("partner_id", 1)])
        await self.dates_collection.create_index("utc_timestamp")
        await self.dates_collection.create_index("status")

    async def _get_partner_id(self, user_id: str) -> Optional[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return user["partner"]["user_id"]
        return None

    async def create_date(self, user_id: str, payload: DateCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id:
            raise ValueError("You must be aligned with a partner to create dates.")

        utc_ts = parse_date_time(payload.date, payload.time, payload.timezone)
        
        new_doc = payload.model_dump()
        new_doc["creator_id"] = user_id
        new_doc["partner_id"] = partner_id
        new_doc["status"] = DateStatus.PROPOSED
        new_doc["utc_timestamp"] = utc_ts
        new_doc["created_at"] = datetime.now(timezone.utc)
        new_doc["updated_at"] = datetime.now(timezone.utc)
        new_doc["reviews"] = []
        new_doc["notification_fired"] = False

        result = await self.dates_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_date(new_doc, payload.timezone)

    async def get_dates(self, user_id: str, status: Optional[str] = None, page: int = 1, size: int = 10, user_timezone: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        
        query = {"$or": [{"creator_id": user_id}, {"partner_id": user_id}]}
        if status:
            query["status"] = status

        skip = (page - 1) * size
        cursor = self.dates_collection.find(query).sort("utc_timestamp", 1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.dates_collection.count_documents(query)

        return [await self._map_date(d, user_timezone) for d in docs], total

    async def get_date_by_id(self, date_id: str, user_id: str, user_timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        doc = await self.dates_collection.find_one({
            "_id": ObjectId(date_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if doc:
            return await self._map_date(doc, user_timezone)
        return None

    async def update_date(self, date_id: str, user_id: str, payload: DateUpdate) -> Optional[Dict[str, Any]]:
        existing = await self.dates_collection.find_one({"_id": ObjectId(date_id), "creator_id": user_id})
        if not existing:
            raise ValueError("Date not found or you are not the creator.")

        if existing["status"] != DateStatus.PROPOSED:
            raise ValueError("Can only update dates in 'Proposed' status.")

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return await self._map_date(existing, payload.timezone or "UTC")

        if any(k in updates for k in ["date", "time", "timezone"]):
            new_date = updates.get("date", existing["date"])
            new_time = updates.get("time", existing["time"])
            new_tz = updates.get("timezone", existing["timezone"])
            updates["utc_timestamp"] = parse_date_time(new_date, new_time, new_tz)

        updates["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.dates_collection.find_one_and_update(
            {"_id": ObjectId(date_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_date(result, updates.get("timezone", existing["timezone"]))

    async def delete_date(self, date_id: str, user_id: str) -> bool:
        result = await self.dates_collection.delete_one({"_id": ObjectId(date_id), "creator_id": user_id})
        return result.deleted_count > 0

    async def respond_to_date(self, date_id: str, user_id: str, response: DateRespond) -> Dict[str, Any]:
        doc = await self.dates_collection.find_one({"_id": ObjectId(date_id), "partner_id": user_id})
        if not doc:
            raise ValueError("Date not found or you are not the recipient.")

        if doc["status"] != DateStatus.PROPOSED:
            raise ValueError("Date already responded to.")

        new_status = DateStatus.ACCEPTED if response.accept else DateStatus.REJECTED
        
        result = await self.dates_collection.find_one_and_update(
            {"_id": ObjectId(date_id)},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_date(result, doc["timezone"])

    async def complete_date(self, date_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.dates_collection.find_one({
            "_id": ObjectId(date_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if not doc:
            raise ValueError("Date not found.")

        if doc["status"] != DateStatus.ACCEPTED:
            raise ValueError("Only accepted dates can be marked completed.")

        now = datetime.now(timezone.utc)
        if now < doc["utc_timestamp"].replace(tzinfo=timezone.utc) if doc["utc_timestamp"].tzinfo is None else now < doc["utc_timestamp"]:
            raise ValueError("Date cannot be completed before its starting time.")

        result = await self.dates_collection.find_one_and_update(
            {"_id": ObjectId(date_id)},
            {"$set": {"status": DateStatus.COMPLETED, "updated_at": now}},
            return_document=True
        )
        return await self._map_date(result, doc["timezone"])

    async def add_review(self, date_id: str, user_id: str, review_payload: DateReviewCreate) -> Dict[str, Any]:
        doc = await self.dates_collection.find_one({
            "_id": ObjectId(date_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if not doc:
            raise ValueError("Date not found.")

        if doc["status"] != DateStatus.COMPLETED:
            raise ValueError("Reviews can only be added to completed dates.")

        # Check if user already reviewed
        for r in doc.get("reviews", []):
            if r["user_id"] == user_id:
                raise ValueError("You have already reviewed this date.")

        review = {
            "user_id": user_id,
            "rating": review_payload.rating,
            "text": review_payload.text
        }

        result = await self.dates_collection.find_one_and_update(
            {"_id": ObjectId(date_id)},
            {"$push": {"reviews": review}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_date(result, doc["timezone"])

    async def _get_names(self, user_id: str, partner_id: str) -> Dict[str, str]:
        names = {user_id: "User", partner_id: "Partner"}
        async for user in self.users.find({"_id": {"$in": [ObjectId(user_id), ObjectId(partner_id)]}}):
            names[str(user["_id"])] = user.get("name", "User")
        return names

    async def get_date_reviews(self, date_id: str, user_id: str, user_timezone: str = "UTC") -> List[Dict[str, Any]]:
        doc = await self.dates_collection.find_one({
            "_id": ObjectId(date_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if not doc:
            raise ValueError("Date not found.")
        
        names = await self._get_names(doc["creator_id"], doc["partner_id"])
        
        results = []
        for r in doc.get("reviews", []):
            results.append({
                "user_id": r["user_id"],
                "user_name": names.get(r["user_id"], "User"),
                "rating": r["rating"],
                "text": r["text"]
            })
        return results

    async def _map_date(self, d: Dict[str, Any], user_timezone: str = "UTC") -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        if "_id" in d: del d["_id"]
        
        # Timezone conversion for date timestamps
        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        for field in ["utc_timestamp", "created_at", "updated_at"]:
            dt = d.get(field)
            if isinstance(dt, datetime):
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)

        # Add names to reviews if they exist
        if d.get("reviews"):
            names = await self._get_names(d["creator_id"], d["partner_id"])
            for r in d["reviews"]:
                r["user_name"] = names.get(r["user_id"], "User")

        # Dynamic Notification Logic:
        # If accepted and time reached, fire notification (logic flag)
        now = datetime.now(timezone.utc)
        if d["status"] == DateStatus.ACCEPTED and not d.get("notification_fired"):
            time_reached = now >= d["utc_timestamp"].replace(tzinfo=timezone.utc) if d["utc_timestamp"].tzinfo is None else now >= d["utc_timestamp"]
            if time_reached:
                d["notification_fired"] = True
                # In a real system, we would update DB here or trigger push
        
        return d

date_service = DateService()
