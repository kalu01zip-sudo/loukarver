import re
import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.schemas.ideas import IdeaCreate, IdeaUpdate

def parse_idea_time(time_str: str) -> timedelta:
    """Parses strings like '2 Hours', '1.5 Hours', '30 Minutes' into timedelta."""
    time_str = time_str.lower()
    
    # Check for hours
    hours_match = re.search(r"(\d+(\.\d+)?)\s*hour", time_str)
    if hours_match:
        return timedelta(hours=float(hours_match.group(1)))
    
    # Check for minutes
    minutes_match = re.search(r"(\d+)\s*minute", time_str)
    if minutes_match:
        return timedelta(minutes=int(minutes_match.group(1)))
        
    return timedelta(hours=1) # Default to 1 hour if unparseable

class IdeaService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.global_ideas = self.db["global_ideas"]
        self.personalized_ideas = self.db["personalized_ideas"]
        self.idea_progress = self.db["idea_progress"]
        self.users = self.db["users"]

    async def init_indexes(self):
        # TTL Index for personalized ideas and progress - expire after 24 hours
        await self.personalized_ideas.create_index("created_at", expireAfterSeconds=86400)
        await self.idea_progress.create_index("created_at", expireAfterSeconds=86400)

    async def seed_defaults(self):
        count = await self.global_ideas.count_documents({})
        if count == 0:
            defaults = [
                {"name": "Sunset Picnic", "time": "2 Hours", "tagline": "A romantic evening by the lake.", "category": "Romance"},
                {"name": "Morning Hike", "time": "3 Hours", "tagline": "Fresh air and great views.", "category": "Adventure"},
                {"name": "Stargazing", "time": "1 Hour", "tagline": "Counting stars together.", "category": "Quiet Time"},
                {"name": "Cook a New Dish", "time": "1.5 Hours", "tagline": "Experiment with flavors.", "category": "Creative"},
                {"name": "Board Game Night", "time": "2 Hours", "tagline": "Friendly competition.", "category": "Fun"},
                {"name": "Visit a Museum", "time": "3 Hours", "tagline": "Explore art and history.", "category": "Culture"},
                {"name": "DIY Project", "time": "4 Hours", "tagline": "Build something together.", "category": "Productive"},
                {"name": "Spa Day at Home", "time": "2 Hours", "tagline": "Relax and recharge.", "category": "Self-Care"}
            ]
            await self.global_ideas.insert_many(defaults)

    async def _get_partner_id(self, user_id: str) -> Optional[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return user["partner"]["user_id"]
        return None

    async def _get_names(self, user_id: str, partner_id: Optional[str]) -> Tuple[str, str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        u_name = user.get("name", "User") if user else "User"
        p_name = "Partner"
        if partner_id:
            pt = await self.users.find_one({"_id": ObjectId(partner_id)})
            if pt:
                p_name = pt.get("name", "Partner")
        return u_name, p_name

    # --- Idea CRUD ---

    async def get_browse_ideas(self, user_id: str, page: int = 1, size: int = 10) -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)

        skip = (page - 1) * size

        pipeline = [
            {"$addFields": {"is_personalized": False, "user_id": None}},
            {
                "$unionWith": {
                    "coll": "personalized_ideas",
                    "pipeline": [
                        {"$match": {"user_id": {"$in": user_ids}}},
                        {"$addFields": {"is_personalized": True}}
                    ]
                }
            },
            {"$sort": {"name": 1}},
            {
                "$facet": {
                    "data": [{"$skip": skip}, {"$limit": size}],
                    "total": [{"$count": "count"}]
                }
            }
        ]

        result = await self.global_ideas.aggregate(pipeline).to_list(length=1)
        data = result[0]["data"]
        total = result[0]["total"][0]["count"] if result[0]["total"] else 0

        for d in data:
            d["id"] = str(d["_id"])
            del d["_id"]
        
        return data, total

    async def create_personalized_idea(self, user_id: str, payload: IdeaCreate) -> Dict[str, Any]:
        new_doc = payload.model_dump()
        new_doc["user_id"] = user_id
        new_doc["created_at"] = datetime.now(timezone.utc)
        
        result = await self.personalized_ideas.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def update_personalized_idea(self, log_id: str, user_id: str, payload: IdeaUpdate) -> Optional[Dict[str, Any]]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)

        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return None

        result = await self.personalized_ideas.find_one_and_update(
            {"_id": ObjectId(log_id), "user_id": {"$in": user_ids}},
            {"$set": updates},
            return_document=True
        )
        if result:
            result["id"] = str(result["_id"])
            del result["_id"]
            return result
        return None

    async def delete_personalized_idea(self, log_id: str, user_id: str) -> bool:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)

        result = await self.personalized_ideas.delete_one({"_id": ObjectId(log_id), "user_id": {"$in": user_ids}})
        return result.deleted_count > 0

    async def get_categories(self, user_id: str) -> List[str]:
        partner_id = await self._get_partner_id(user_id)
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)

        global_cats = await self.global_ideas.distinct("category")
        personal_cats = await self.personalized_ideas.distinct("category", {"user_id": {"$in": user_ids}})
        
        return sorted(list(set(global_cats + personal_cats)))

    # --- Idea Selection & Progress ---

    async def select_idea(self, idea_id: str, user_id: str) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id:
            raise ValueError("Partner alignment required to select ideas.")

        idea = await self.global_ideas.find_one({"_id": ObjectId(idea_id)})
        if not idea:
            user_ids = [user_id, partner_id]
            idea = await self.personalized_ideas.find_one({"_id": ObjectId(idea_id), "user_id": {"$in": user_ids}})

        if not idea:
            raise ValueError("Idea not found.")

        couple_user_ids = sorted([user_id, partner_id])
        
        # Check if already active/selected
        existing = await self.idea_progress.find_one({
            "idea_id": idea_id,
            "user_ids": couple_user_ids,
            "is_completed": False,
            "is_expired": False
        })
        if existing:
            return await self._map_progress_doc(existing, user_id)

        now = datetime.now(timezone.utc)
        progress_doc = {
            "idea_id": idea_id,
            "user_ids": couple_user_ids,
            "name": idea["name"],
            "time": idea["time"],
            "tagline": idea["tagline"],
            "category": idea["category"],
            # Acceptance
            "is_accepted_user_1": False,
            "is_accepted_user_2": False,
            "accepted_at_user_1": None,
            "accepted_at_user_2": None,
            # Countdown
            "countdown_start": None,
            "countdown_end": None,
            # Completion
            "is_done_user_1": False,
            "is_done_user_2": False,
            "done_at_user_1": None,
            "done_at_user_2": None,
            "completed_in_user_1": None,
            "completed_in_user_2": None,
            # Meta
            "created_at": now,
            "is_completed": False,
            "is_expired": False
        }
        
        # Current user auto-accepts? No, user said "partner also have a option to accept". 
        # Usually initiator accepts. Let's make initiator auto-accept for UX, or manual.
        # User said "partner also have a option to accept the idea, When both of user and partner accept the ideas countdown begin."
        # I'll make the initiator auto-accept.
        idx = couple_user_ids.index(user_id)
        progress_doc[f"is_accepted_user_{idx+1}"] = True
        progress_doc[f"accepted_at_user_{idx+1}"] = now

        result = await self.idea_progress.insert_one(progress_doc)
        progress_doc["id"] = str(result.inserted_id)
        return await self._map_progress_doc(progress_doc, user_id)

    async def accept_idea(self, progress_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.idea_progress.find_one({"_id": ObjectId(progress_id)})
        if not doc:
            raise ValueError("Idea progress not found.")
        if user_id not in doc["user_ids"]:
            raise PermissionError("Not authorized.")

        idx = doc["user_ids"].index(user_id)
        now = datetime.now(timezone.utc)
        
        updates = {
            f"is_accepted_user_{idx+1}": True,
            f"accepted_at_user_{idx+1}": now
        }

        partner_idx = 1 - idx
        if doc[f"is_accepted_user_{partner_idx+1}"]:
            # Both accepted! Start countdown
            duration = parse_idea_time(doc["time"])
            updates["countdown_start"] = now
            updates["countdown_end"] = now + duration

        result = await self.idea_progress.find_one_and_update(
            {"_id": ObjectId(progress_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_progress_doc(result, user_id)

    async def mark_idea_done(self, progress_id: str, user_id: str) -> Dict[str, Any]:
        doc = await self.idea_progress.find_one({"_id": ObjectId(progress_id)})
        if not doc:
            raise ValueError("Idea progress not found.")
        if user_id not in doc["user_ids"]:
            raise PermissionError("Not authorized.")
        
        if not doc["countdown_start"]:
            raise ValueError("Idea must be accepted by both before completion.")

        now = datetime.now(timezone.utc)
        if doc["countdown_end"] and now > doc["countdown_end"].replace(tzinfo=timezone.utc if doc["countdown_end"].tzinfo is None else doc["countdown_end"].tzinfo):
             # Handled in mapping/getters, but let's be explicit
             pass

        idx = doc["user_ids"].index(user_id)
        
        # Calculate completed_in
        start = doc["countdown_start"]
        if start.tzinfo is None: start = start.replace(tzinfo=timezone.utc)
        diff = now - start
        hours, remainder = divmod(diff.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        comp_time = f"{int(hours)}h {int(minutes)}m"

        updates = {
            f"is_done_user_{idx+1}": True,
            f"done_at_user_{idx+1}": now,
            f"completed_in_user_{idx+1}": comp_time
        }

        # Check if both done
        partner_idx = 1 - idx
        if doc[f"is_done_user_{partner_idx+1}"]:
            updates["is_completed"] = True

        result = await self.idea_progress.find_one_and_update(
            {"_id": ObjectId(progress_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_progress_doc(result, user_id)

    # --- Filtered Getters ---

    async def get_paginated_progress(self, user_id: str, status_type: str, page: int = 1, size: int = 10, viewer_timezone: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        couple_user_ids = sorted([user_id, partner_id]) if partner_id else [user_id]
        
        now = datetime.now(timezone.utc)
        query = {"user_ids": couple_user_ids}

        if status_type == "active":
            # Active: Not completed AND (Not started OR Not expired)
            query["is_completed"] = False
            query["$or"] = [
                {"countdown_end": None},
                {"countdown_end": {"$gt": now}}
            ]
        elif status_type == "completed":
            query["is_completed"] = True
        elif status_type == "incomplete":
            # Incomplete: Not completed AND expired
            query["is_completed"] = False
            query["countdown_end"] = {"$lte": now}

        skip = (page - 1) * size
        cursor = self.idea_progress.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.idea_progress.count_documents(query)

        results = []
        for d in docs:
            results.append(await self._map_progress_doc(d, user_id, viewer_timezone))
        
        return results, total

    async def _map_progress_doc(self, d: Dict[str, Any], user_id: str, viewer_timezone: str = "UTC") -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        
        idx = d["user_ids"].index(user_id)
        partner_idx = 1 - idx if len(d["user_ids"]) > 1 else None
        
        partner_id = d["user_ids"][partner_idx] if partner_idx is not None else None
        user_name, partner_name = await self._get_names(user_id, partner_id)

        d["user_name"] = user_name
        d["partner_name"] = partner_name

        # Acceptance
        d["is_accepted_user"] = d[f"is_accepted_user_{idx+1}"]
        d["is_accepted_partner"] = d[f"is_accepted_user_{partner_idx+1}"] if partner_idx is not None else False
        d["accepted_at_user"] = d[f"accepted_at_user_{idx+1}"]
        d["accepted_at_partner"] = d[f"accepted_at_user_{partner_idx+1}"] if partner_idx is not None else None

        # Completion
        d["is_done_user"] = d[f"is_done_user_{idx+1}"]
        d["is_done_partner"] = d[f"is_done_user_{partner_idx+1}"] if partner_idx is not None else False
        d["done_at_user"] = d[f"done_at_user_{idx+1}"]
        d["done_at_partner"] = d[f"done_at_user_{partner_idx+1}"] if partner_idx is not None else None
        d["completed_in_user"] = d[f"completed_in_user_{idx+1}"]
        d["completed_in_partner"] = d[f"completed_in_user_{partner_idx+1}"] if partner_idx is not None else None

        # Expired check
        now = datetime.now(timezone.utc)
        if not d["is_completed"] and d["countdown_end"]:
            end = d["countdown_end"]
            if end.tzinfo is None: end = end.replace(tzinfo=timezone.utc)
            if now > end:
                d["is_expired"] = True

        # Timezone conversion for all datetime fields
        try:
            tz = zoneinfo.ZoneInfo(viewer_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        date_fields = [
            "accepted_at_user", "accepted_at_partner", 
            "countdown_start", "countdown_end", 
            "done_at_user", "done_at_partner", 
            "created_at"
        ]
        for field in date_fields:
            if d.get(field) and isinstance(d[field], datetime):
                dt = d[field]
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)
        
        return d

idea_service = IdeaService()
