from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.energy import EnergyCreate, EnergyUpdate, EnergyPatchShare

class EnergyService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.energy_logs = self.db["energy_logs"]
        self.users = self.db["users"]

    async def create_energy_log(self, user_id: str, payload: EnergyCreate) -> Dict[str, Any]:
        new_doc = payload.model_dump()
        new_doc["user_id"] = user_id
        new_doc["created_at"] = datetime.now(timezone.utc)
        new_doc["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.energy_logs.insert_one(new_doc)
        new_doc["id"] = str(result.inserted_id)
        return new_doc

    async def get_energy_logs(self, user_id: str) -> List[Dict[str, Any]]:
        cursor = self.energy_logs.find({"user_id": user_id}).sort("created_at", -1)
        docs = await cursor.to_list(length=None)
        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            results.append(d)
        return results

    async def get_energy_log(self, log_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        doc = await self.energy_logs.find_one({"_id": ObjectId(log_id), "user_id": user_id})
        if doc:
            doc["id"] = str(doc["_id"])
            del doc["_id"]
            return doc
        return None

    async def update_energy_log(self, log_id: str, user_id: str, payload: EnergyUpdate) -> Optional[Dict[str, Any]]:
        updates = {k: v for k, v in payload.model_dump().items() if v is not None}
        if not updates:
            return await self.get_energy_log(log_id, user_id)
            
        updates["updated_at"] = datetime.now(timezone.utc)
        
        result = await self.energy_logs.find_one_and_update(
            {"_id": ObjectId(log_id), "user_id": user_id},
            {"$set": updates},
            return_document=True
        )
        if result:
            result["id"] = str(result["_id"])
            del result["_id"]
            return result
        return None

    async def delete_energy_log(self, log_id: str, user_id: str) -> bool:
        result = await self.energy_logs.delete_one({"_id": ObjectId(log_id), "user_id": user_id})
        return result.deleted_count > 0

    async def patch_share_status(self, log_id: str, user_id: str, payload: EnergyPatchShare) -> bool:
        result = await self.energy_logs.update_one(
            {"_id": ObjectId(log_id), "user_id": user_id},
            {"$set": {
                "share_with_partner": payload.share_with_partner,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return result.matched_count > 0

    async def get_partner_energy(self, user_id: str) -> List[Dict[str, Any]]:
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("partner"):
            return []
            
        partner_id = user["partner"]["user_id"]
        cursor = self.energy_logs.find({
            "user_id": partner_id,
            "share_with_partner": True
        }).sort("created_at", -1).limit(10)
        
        docs = await cursor.to_list(length=None)
        results = []
        for d in docs:
            d["id"] = str(d["_id"])
            del d["_id"]
            results.append(d)
        return results

energy_service = EnergyService()
