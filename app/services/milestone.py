import uuid
import zoneinfo
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.milestone import (
    MilestoneCreate, MilestoneUpdate, MilestoneStepCreate, MilestoneStepUpdate
)

class MilestoneService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.milestones_collection = self.db["milestone_goals"]
        self.users = self.db["users"]

    async def init_indexes(self):
        await self.milestones_collection.create_index([("creator_id", 1), ("partner_id", 1)])
        await self.milestones_collection.create_index("created_at")

    async def _get_partner_id(self, user_id: str) -> Optional[str]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_aligned") and user.get("partner"):
            return user["partner"]["user_id"]
        return None

    async def create_milestone(self, user_id: str, payload: MilestoneCreate) -> Dict[str, Any]:
        partner_id = await self._get_partner_id(user_id)
        if not partner_id:
            raise ValueError("You must be aligned with a partner to create milestones.")

        steps = []
        for s in payload.steps:
            steps.append({
                "id": str(uuid.uuid4()),
                "text": s.text,
                "is_completed": False
            })

        new_doc = {
            "creator_id": user_id,
            "partner_id": partner_id,
            "name": payload.name,
            "why_it_matters": payload.why_it_matters,
            "is_private": payload.is_private,
            "pin": payload.pin if payload.is_private else None,
            "steps": steps,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }

        result = await self.milestones_collection.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return await self._map_milestone(new_doc, user_timezone=payload.timezone)

    async def get_milestones(self, user_id: str, page: int = 1, size: int = 20, pin: Optional[str] = None, user_timezone: str = "UTC") -> Tuple[List[Dict[str, Any]], int]:
        partner_id = await self._get_partner_id(user_id)
        query = {"$or": [{"creator_id": user_id}, {"partner_id": user_id}]}
        
        skip = (page - 1) * size
        cursor = self.milestones_collection.find(query).sort("created_at", -1).skip(skip).limit(size)
        docs = await cursor.to_list(length=None)
        total = await self.milestones_collection.count_documents(query)

        results = []
        for d in docs:
            results.append(await self._map_milestone(d, pin, user_timezone))
        return results, total

    async def get_milestone_by_id(self, milestone_id: str, user_id: str, pin: Optional[str] = None, user_timezone: str = "UTC") -> Optional[Dict[str, Any]]:
        doc = await self.milestones_collection.find_one({
            "_id": ObjectId(milestone_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if doc:
            return await self._map_milestone(doc, pin, user_timezone)
        return None

    async def update_milestone(self, milestone_id: str, user_id: str, payload: MilestoneUpdate) -> Dict[str, Any]:
        doc = await self.milestones_collection.find_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Milestone not found or you are not the creator.")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return await self._map_milestone(doc, user_timezone=payload.timezone)

        updates["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.milestones_collection.find_one_and_update(
            {"_id": ObjectId(milestone_id)},
            {"$set": updates},
            return_document=True
        )
        return await self._map_milestone(result, user_timezone=payload.timezone)

    async def delete_milestone(self, milestone_id: str, user_id: str, pin: Optional[str] = None) -> bool:
        doc = await self.milestones_collection.find_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        if not doc:
            return False

        if doc.get("is_private") and doc.get("pin") != pin:
            raise ValueError("Incorrect PIN for private milestone.")

        result = await self.milestones_collection.delete_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        return result.deleted_count > 0

    # --- Step Management ---

    async def add_step(self, milestone_id: str, user_id: str, step_payload: MilestoneStepCreate) -> Dict[str, Any]:
        doc = await self.milestones_collection.find_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Milestone not found or you are not the creator.")

        new_step = {
            "id": str(uuid.uuid4()),
            "text": step_payload.text,
            "is_completed": False
        }

        result = await self.milestones_collection.find_one_and_update(
            {"_id": ObjectId(milestone_id)},
            {"$push": {"steps": new_step}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_milestone(result, user_timezone=step_payload.timezone)

    async def update_step(self, milestone_id: str, step_id: str, user_id: str, step_payload: MilestoneStepUpdate) -> Dict[str, Any]:
        doc = await self.milestones_collection.find_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Milestone not found or you are not the creator.")

        updates = {}
        if step_payload.text is not None:
            updates["steps.$.text"] = step_payload.text
        if step_payload.is_completed is not None:
            updates["steps.$.is_completed"] = step_payload.is_completed
            if step_payload.is_completed:
                updates["steps.$.completed_by"] = user_id
                updates["steps.$.completed_at"] = datetime.now(timezone.utc)

        if not updates:
            return self._map_milestone(doc, user_timezone=step_payload.timezone)

        result = await self.milestones_collection.find_one_and_update(
            {"_id": ObjectId(milestone_id), "steps.id": step_id},
            {"$set": updates},
            return_document=True
        )
        return await self._map_milestone(result, user_timezone=step_payload.timezone)

    async def delete_step(self, milestone_id: str, step_id: str, user_id: str, pin: Optional[str] = None, user_timezone: str = "UTC") -> Dict[str, Any]:
        doc = await self.milestones_collection.find_one({"_id": ObjectId(milestone_id), "creator_id": user_id})
        if not doc:
            raise ValueError("Milestone not found or you are not the creator.")

        if doc.get("is_private") and doc.get("pin") != pin:
            raise ValueError("Incorrect PIN for private milestone.")

        result = await self.milestones_collection.find_one_and_update(
            {"_id": ObjectId(milestone_id)},
            {"$pull": {"steps": {"id": step_id}}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            return_document=True
        )
        return await self._map_milestone(result, user_timezone=user_timezone)

    async def toggle_step_completion(self, milestone_id: str, step_id: str, user_id: str, user_timezone: str = "UTC") -> Dict[str, Any]:
        doc = await self.milestones_collection.find_one({
            "_id": ObjectId(milestone_id),
            "$or": [{"creator_id": user_id}, {"partner_id": user_id}]
        })
        if not doc:
            raise ValueError("Milestone not found.")

        # Find current state
        current_step = next((s for s in doc["steps"] if s["id"] == step_id), None)
        if not current_step:
            raise ValueError("Step not found.")

        new_status = not current_step.get("is_completed", False)
        
        updates = {"steps.$.is_completed": new_status}
        if new_status:
            updates["steps.$.completed_by"] = user_id
            updates["steps.$.completed_at"] = datetime.now(timezone.utc)
        else:
            updates["steps.$.completed_by"] = None
            updates["steps.$.completed_at"] = None

        result = await self.milestones_collection.find_one_and_update(
            {"_id": ObjectId(milestone_id), "steps.id": step_id},
            {"$set": updates},
            return_document=True
        )
        return await self._map_milestone(result, user_timezone=user_timezone)

    async def _get_names(self, user_id: str, partner_id: str) -> Dict[str, str]:
        names = {user_id: "User", partner_id: "Partner"}
        async for user in self.users.find({"_id": {"$in": [ObjectId(user_id), ObjectId(partner_id)]}}):
            names[str(user["_id"])] = user.get("name", "User")
        return names

    async def _map_milestone(self, d: Dict[str, Any], pin: Optional[str] = None, user_timezone: str = "UTC") -> Dict[str, Any]:
        d["id"] = str(d["_id"])
        if "_id" in d: del d["_id"]
        
        # Ensure string IDs
        creator_id = str(d.get("creator_id", ""))
        partner_id = str(d.get("partner_id", ""))
        d["creator_id"] = creator_id
        d["partner_id"] = partner_id

        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")

        is_locked = False
        if d.get("is_private") and d.get("pin") != pin:
            is_locked = True
            # Mask sensitive data if locked
            d["name"] = "Private Milestone"
            d["why_it_matters"] = "Locked"
            d["steps"] = []
            d["progress"] = 0.0
            d["is_completed"] = False
        else:
            names = await self._get_names(creator_id, partner_id)
            # Calculate progress
            steps = d.get("steps", [])
            total = len(steps)
            completed = 0
            for s in steps:
                if s.get("is_completed"):
                    completed += 1
                    # Convert step timestamp
                    dt = s.get("completed_at")
                    if isinstance(dt, datetime):
                        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                        s["completed_at"] = dt.astimezone(tz)
                    
                    # Add completed_by_name
                    c_id = s.get("completed_by")
                    if c_id:
                        s["completed_by_name"] = names.get(str(c_id), "User")
            
            d["progress"] = (completed / total * 100) if total > 0 else 100.0
            d["is_completed"] = (completed == total) if total > 0 else True

        # Timezone conversion for milestone timestamps
        for field in ["created_at", "updated_at"]:
            dt = d.get(field)
            if isinstance(dt, datetime):
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
                d[field] = dt.astimezone(tz)
            else:
                d[field] = datetime.now(tz)

        d["is_locked"] = is_locked
        if "pin" in d: del d["pin"] # Never return pin in response
        
        return d

milestone_service = MilestoneService()
