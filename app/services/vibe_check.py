import random
import string
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.vibe_check import VibeCheckProfileCreate

class VibeCheckService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.profiles = self.db["vibe_check_profiles"]
        self.connections = self.db["vibe_check_connections"]
        self.requests = self.db["vibe_check_requests"]

    async def init_indexes(self):
        await self.profiles.create_index("user_id", unique=True)
        await self.profiles.create_index("vibe_key", unique=True)
        await self.connections.create_index([("user_id", 1), ("partner_id", 1)], unique=True)
        await self.requests.create_index([("sender_id", 1), ("recipient_id", 1)], unique=True)
        await self.requests.create_index("recipient_id")

    async def generate_unique_vibe_key(self) -> str:
        """Generates a unique 12-character vibe key like VIBE-X7R2P9."""
        while True:
            random_part = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            vibe_key = f"VIBE-{random_part}"
            existing = await self.profiles.find_one({"vibe_key": vibe_key})
            if not existing:
                return vibe_key

    async def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        doc = await self.profiles.find_one({"user_id": user_id})
        if doc:
            # AUTO-FIX: If vibe_key is missing for some reason, generate and save it
            if not doc.get("vibe_key"):
                vibe_key = await self.generate_unique_vibe_key()
                await self.profiles.update_one(
                    {"_id": doc["_id"]},
                    {"$set": {"vibe_key": vibe_key, "updated_at": datetime.now(timezone.utc)}}
                )
                doc["vibe_key"] = vibe_key
                
            doc["id"] = str(doc["_id"])
            return doc
        return None

    async def create_or_update_profile(self, user_id: str, payload: VibeCheckProfileCreate) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        existing = await self.profiles.find_one({"user_id": user_id})
        
        if existing:
            update_data = {"name": payload.name, "updated_at": now}
            if not existing.get("vibe_key"):
                update_data["vibe_key"] = await self.generate_unique_vibe_key()
                
            result = await self.profiles.find_one_and_update(
                {"user_id": user_id},
                {"$set": update_data},
                return_document=True
            )
        else:
            vibe_key = await self.generate_unique_vibe_key()
            doc = {
                "user_id": user_id,
                "name": payload.name,
                "vibe_key": vibe_key,
                "created_at": now,
                "updated_at": now
            }
            await self.profiles.insert_one(doc)
            result = doc

        result["id"] = str(result["_id"])
        return result

    async def get_connections(self, user_id: str) -> List[Dict[str, Any]]:
        """List all people this user is connected with in VibeCheck."""
        cursor = self.connections.find({"user_id": user_id})
        connection_docs = await cursor.to_list(length=None)
        
        partner_ids = [c["partner_id"] for c in connection_docs]
        partner_profiles = await self.profiles.find({"user_id": {"$in": partner_ids}}).to_list(length=None)
        profile_map = {p["user_id"]: p["name"] for p in partner_profiles}
        
        results = []
        for c in connection_docs:
            results.append({
                "user_id": c["partner_id"],
                "name": profile_map.get(c["partner_id"], "Unknown User"),
                "connected_at": c["connected_at"]
            })
        return results

    async def connect_with_partner(self, user_id: str, vibe_key: str) -> Dict[str, Any]:
        """Create a pending connection request using a Vibe Key."""
        # 1. Fetch initiator profile
        initiator = await self.profiles.find_one({"user_id": user_id})
        if not initiator:
            raise ValueError("Your VibeCheck profile is not setup.")

        # 2. Fetch target profile
        target = await self.profiles.find_one({"vibe_key": vibe_key})
        if not target:
            raise ValueError("User with this Vibe Key not found.")
            
        if target["user_id"] == user_id:
            raise ValueError("You cannot connect with yourself.")

        # 3. Check if already connected
        existing_conn = await self.connections.find_one({"user_id": user_id, "partner_id": target["user_id"]})
        if existing_conn:
            raise ValueError(f"You are already connected with {target['name']}.")

        now = datetime.now(timezone.utc)
        
        # 4. Create pending request
        await self.requests.update_one(
            {"sender_id": user_id, "recipient_id": target["user_id"]},
            {"$setOnInsert": {
                "sender_id": user_id, 
                "recipient_id": target["user_id"], 
                "sender_name": initiator["name"],
                "created_at": now
            }},
            upsert=True
        )

        return {"success": True, "message": f"Connection request sent to {target['name']}."}

    async def get_pending_requests(self, user_id: str) -> List[Dict[str, Any]]:
        """List all pending connection requests for this user."""
        cursor = self.requests.find({"recipient_id": user_id})
        docs = await cursor.to_list(length=None)
        
        results = []
        for d in docs:
            results.append({
                "request_id": str(d["_id"]),
                "sender_id": d["sender_id"],
                "sender_name": d["sender_name"],
                "created_at": d["created_at"]
            })
        return results

    async def respond_to_request(self, user_id: str, request_id: str, accept: bool) -> Dict[str, Any]:
        """Accept or reject a pending connection request."""
        request = await self.requests.find_one({"_id": ObjectId(request_id), "recipient_id": user_id})
        if not request:
            raise ValueError("Request not found.")

        if accept:
            now = datetime.now(timezone.utc)
            # Create mutual connections
            # Recipient -> Sender
            await self.connections.update_one(
                {"user_id": user_id, "partner_id": request["sender_id"]},
                {"$setOnInsert": {"user_id": user_id, "partner_id": request["sender_id"], "connected_at": now}},
                upsert=True
            )
            # Sender -> Recipient
            await self.connections.update_one(
                {"user_id": request["sender_id"], "partner_id": user_id},
                {"$setOnInsert": {"user_id": request["sender_id"], "partner_id": user_id, "connected_at": now}},
                upsert=True
            )
            message = "Connection accepted."
        else:
            message = "Connection request rejected."

        # Delete the request
        await self.requests.delete_one({"_id": ObjectId(request_id)})
        
        return {"success": True, "message": message}

    async def delete_connection(self, user_id: str, partner_id: str) -> bool:
        """Remove a mutual connection between two users."""
        # A -> B
        res1 = await self.connections.delete_one({"user_id": user_id, "partner_id": partner_id})
        # B -> A
        res2 = await self.connections.delete_one({"user_id": partner_id, "partner_id": user_id})
        return res1.deleted_count > 0 or res2.deleted_count > 0

    async def regenerate_vibe_key(self, user_id: str) -> str:
        """Generate a new unique vibe key for the user."""
        new_key = await self.generate_unique_vibe_key()
        result = await self.profiles.update_one(
            {"user_id": user_id},
            {"$set": {"vibe_key": new_key, "updated_at": datetime.now(timezone.utc)}}
        )
        if result.matched_count == 0:
            raise ValueError("VibeCheck profile not found.")
        return new_key

vibe_check_service = VibeCheckService()
