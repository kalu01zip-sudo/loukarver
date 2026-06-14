from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.mood import MoodListCreate, MoodListUpdate, MoodLogCreate, MoodLogUpdate

class MoodService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.mood_list = self.db["mood_list"]
        self.mood_history = self.db["mood_history"]
        self.users = self.db["users"]

    async def seed_defaults(self):
        count = await self.mood_list.count_documents({"couple_id": {"$exists": False}})
        if count == 0:
            defaults = [
                {"name": "At peace", "symbol": "◯", "order_index": 1, "is_active": True},
                {"name": "Loving", "symbol": "◈", "order_index": 2, "is_active": True},
                {"name": "Flirtatious", "symbol": "✦", "order_index": 3, "is_active": True},
                {"name": "Passionate", "symbol": "◆", "order_index": 4, "is_active": True},
                {"name": "Needing you", "symbol": "✧", "order_index": 5, "is_active": True},
                {"name": "Thinking of you", "symbol": "·", "order_index": 6, "is_active": True}
            ]
            await self.mood_list.insert_many(defaults)

    # --- Scoping & Helper Functions ---

    async def _get_couple_id(self, user_id: str) -> str:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            return user_id
        if user.get("is_aligned") and user.get("partner"):
            partner_id = user["partner"]["user_id"]
            couple_id = "_".join(sorted([user_id, partner_id]))
            
            # Migration check: if they just aligned, check if a custom list exists for couple_id
            couple_exists = await self.mood_list.count_documents({"couple_id": couple_id})
            if couple_exists == 0:
                # Check if initiator (user_id) has a custom list
                user_exists = await self.mood_list.count_documents({"couple_id": user_id})
                if user_exists > 0:
                    await self.mood_list.update_many({"couple_id": user_id}, {"$set": {"couple_id": couple_id}})
                
                # Check if partner has a custom list
                partner_exists = await self.mood_list.count_documents({"couple_id": partner_id})
                if partner_exists > 0:
                    if user_exists > 0:
                        # Merge by deleting partner's list to avoid duplicate records
                        await self.mood_list.delete_many({"couple_id": partner_id})
                    else:
                        await self.mood_list.update_many({"couple_id": partner_id}, {"$set": {"couple_id": couple_id}})
            return couple_id
        return user_id

    async def _ensure_custom_mood_list(self, couple_id: str) -> None:
        count = await self.mood_list.count_documents({"couple_id": couple_id})
        if count > 0:
            return
            
        cursor = self.mood_list.find({"couple_id": {"$exists": False}, "is_active": True}).sort("order_index", 1)
        defaults = await cursor.to_list(length=None)
        
        if not defaults:
            defaults = [
                {"name": "At peace", "symbol": "◯", "order_index": 1, "is_active": True},
                {"name": "Loving", "symbol": "◈", "order_index": 2, "is_active": True},
                {"name": "Flirtatious", "symbol": "✦", "order_index": 3, "is_active": True},
                {"name": "Passionate", "symbol": "◆", "order_index": 4, "is_active": True},
                {"name": "Needing you", "symbol": "✧", "order_index": 5, "is_active": True},
                {"name": "Thinking of you", "symbol": "·", "order_index": 6, "is_active": True}
            ]
            
        cloned_moods = []
        for d in defaults:
            cloned = {
                "name": d["name"],
                "symbol": d["symbol"],
                "order_index": d["order_index"],
                "is_active": d["is_active"],
                "couple_id": couple_id,
                "original_default_id": str(d["_id"]) if "_id" in d else None
            }
            cloned_moods.append(cloned)
            
        if cloned_moods:
            await self.mood_list.insert_many(cloned_moods)

    async def _resolve_mood_id(self, couple_id: str, mood_id: str) -> ObjectId:
        try:
            obj_id = ObjectId(mood_id)
        except Exception:
            raise ValueError("Invalid mood ID format")
            
        # 1. Check if the mood is in their custom list
        doc = await self.mood_list.find_one({"_id": obj_id, "couple_id": couple_id})
        if doc:
            return obj_id
            
        # 2. Check if the mood is a clone of a default mood
        doc = await self.mood_list.find_one({"original_default_id": mood_id, "couple_id": couple_id})
        if doc:
            return doc["_id"]
            
        # 3. Check if it's a global default mood (and custom list hasn't been cloned yet)
        global_doc = await self.mood_list.find_one({"_id": obj_id, "couple_id": {"$exists": False}})
        if global_doc:
            await self._ensure_custom_mood_list(couple_id)
            doc = await self.mood_list.find_one({"original_default_id": mood_id, "couple_id": couple_id})
            if doc:
                return doc["_id"]
                
        raise ValueError("Mood option not found")

    # --- Mood List CRUD ---
    
    async def get_mood_list(self, user_id: str) -> List[Dict[str, Any]]:
        couple_id = await self._get_couple_id(user_id)
        count = await self.mood_list.count_documents({"couple_id": couple_id, "is_active": True})
        if count > 0:
            cursor = self.mood_list.find({"couple_id": couple_id, "is_active": True}).sort("order_index", 1)
        else:
            cursor = self.mood_list.find({"couple_id": {"$exists": False}, "is_active": True}).sort("order_index", 1)
            
        docs = await cursor.to_list(length=None)
        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            results.append(d)
        return results

    async def create_mood_option(self, user_id: str, payload: MoodListCreate) -> Dict[str, Any]:
        couple_id = await self._get_couple_id(user_id)
        await self._ensure_custom_mood_list(couple_id)
        
        new_doc = payload.model_dump()
        new_doc["couple_id"] = couple_id
        
        result = await self.mood_list.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def update_mood_option(self, user_id: str, mood_id: str, payload: MoodListUpdate) -> None:
        couple_id = await self._get_couple_id(user_id)
        resolved_id = await self._resolve_mood_id(couple_id, mood_id)
        
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return
        await self.mood_list.update_one({"_id": resolved_id}, {"$set": updates})

    async def delete_mood_option(self, user_id: str, mood_id: str) -> None:
        couple_id = await self._get_couple_id(user_id)
        resolved_id = await self._resolve_mood_id(couple_id, mood_id)
        await self.mood_list.update_one({"_id": resolved_id}, {"$set": {"is_active": False}})


    # --- Mood Input CRUD ---

    async def log_mood(self, user_id: str, payload: MoodLogCreate) -> Dict[str, Any]:
        couple_id = await self._get_couple_id(user_id)
        resolved_id = await self._resolve_mood_id(couple_id, payload.mood_id)
        
        mood_option = await self.mood_list.find_one({"_id": resolved_id})
        if not mood_option:
            raise ValueError("Invalid mood option ID")
            
        new_doc = {
            "user_id": user_id,
            "mood_id": str(resolved_id),
            "mood_name": mood_option["name"],
            "mood_symbol": mood_option["symbol"],
            "created_at": datetime.now(timezone.utc)
        }
        result = await self.mood_history.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def get_mood_history(self, user_id: str) -> List[Dict[str, Any]]:
        cursor = self.mood_history.find({"user_id": user_id}).sort("created_at", -1).limit(50)
        docs = await cursor.to_list(length=None)
        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            results.append(d)
        return results

    async def update_logged_mood(self, log_id: str, user_id: str, payload: MoodLogUpdate) -> None:
        couple_id = await self._get_couple_id(user_id)
        resolved_id = await self._resolve_mood_id(couple_id, payload.mood_id)
        
        mood_option = await self.mood_list.find_one({"_id": resolved_id})
        if not mood_option:
            raise ValueError("Invalid mood option ID")
            
        result = await self.mood_history.update_one(
            {"_id": ObjectId(log_id), "user_id": user_id},
            {"$set": {
                "mood_id": str(resolved_id),
                "mood_name": mood_option["name"],
                "mood_symbol": mood_option["symbol"],
                "created_at": datetime.now(timezone.utc)
            }}
        )
        if result.matched_count == 0:
            raise PermissionError("Mood log not found or not owned by user")

    async def delete_logged_mood(self, log_id: str, user_id: str) -> None:
        result = await self.mood_history.delete_one({"_id": ObjectId(log_id), "user_id": user_id})
        if result.deleted_count == 0:
            raise PermissionError("Mood log not found or not owned by user")


    # --- Current Mood Sync ---

    async def get_current_moods(self, user_id: str) -> List[Dict[str, Any]]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        partner_id = None
        partner_name = "Partner"
        user_name = user.get("name", "Me") if user else "Me"
        
        if user and user.get("partner"):
            partner_id = user["partner"]["user_id"]
            partner_name = user["partner"].get("name", "Partner")
            
        states = []
        
        # User's latest mood
        my_latest = await self.mood_history.find_one({"user_id": user_id}, sort=[("created_at", -1)])
        if my_latest:
            states.append({
                "mood_name": my_latest["mood_name"],
                "mood_symbol": my_latest["mood_symbol"],
                "updated_at": my_latest["created_at"],
                "is_partner": False,
                "author_name": user_name
            })
            
        # Partner's latest mood
        if partner_id:
            pt_latest = await self.mood_history.find_one({"user_id": partner_id}, sort=[("created_at", -1)])
            if pt_latest:
                states.append({
                    "mood_name": pt_latest["mood_name"],
                    "mood_symbol": pt_latest["mood_symbol"],
                    "updated_at": pt_latest["created_at"],
                    "is_partner": True,
                    "author_name": partner_name
                })
                
        return states

mood_service = MoodService()
