from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
from app.core.config import settings
from app.schemas.vibe_pulse import VibePulseSetRequest, PulseStatus, VibePulseResponse, AlignedCheckResponse
from app.services.vibe_check import vibe_check_service

class VibePulseService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.pulses = self.db["vibe_pulses"]
        self.connections = self.db["vibe_check_connections"]
        self.profiles = self.db["vibe_check_profiles"]

    async def init_indexes(self):
        await self.pulses.create_index([("user_id", 1), ("partner_id", 1)], unique=True)
        await self.pulses.create_index("user_id")

    async def set_pulse(self, user_id: str, payload: VibePulseSetRequest) -> Dict[str, Any]:
        # 1. Verify connection
        is_connected = await self.connections.find_one({"user_id": user_id, "partner_id": payload.partner_id})
        if not is_connected:
            raise ValueError("You can only set a Vibe Pulse for connected partners.")

        now = datetime.now(timezone.utc)

        # 2. Special Logic for Aligned
        if payload.status == PulseStatus.ALIGNED:
            # Check if user is already Aligned with someone else
            existing_aligned = await self.pulses.find_one({
                "user_id": user_id,
                "partner_id": {"$ne": payload.partner_id},
                "status": PulseStatus.ALIGNED
            })
            if existing_aligned:
                raise ValueError("You are already Aligned with another person. Please reset that status first.")

        # 3. Update status
        await self.pulses.update_one(
            {"user_id": user_id, "partner_id": payload.partner_id},
            {"$set": {
                "status": payload.status,
                "updated_at": now
            }},
            upsert=True
        )

        return await self.get_pulse_status(user_id, payload.partner_id)

    async def get_pulse_status(self, user_id: str, partner_id: str) -> Dict[str, Any]:
        # Get my status for them
        my_pulse = await self.pulses.find_one({"user_id": user_id, "partner_id": partner_id})
        my_status = my_pulse["status"] if my_pulse else PulseStatus.NONE

        # Get their status for me
        their_pulse = await self.pulses.find_one({"user_id": partner_id, "partner_id": user_id})
        their_status = their_pulse["status"] if their_pulse else PulseStatus.NONE

        partner_profile = await vibe_check_service.get_profile(partner_id)
        
        is_aligned_matched = (my_status == PulseStatus.ALIGNED and their_status == PulseStatus.ALIGNED)

        return {
            "partner_id": partner_id,
            "partner_name": partner_profile["name"] if partner_profile else "Unknown",
            "my_status": my_status,
            "partner_status": their_status,
            "is_aligned_matched": is_aligned_matched,
            "updated_at": my_pulse["updated_at"] if my_pulse else datetime.now(timezone.utc)
        }

    async def get_all_pulses(self, user_id: str) -> List[Dict[str, Any]]:
        # Fetch all my pulses
        cursor = self.pulses.find({"user_id": user_id})
        my_pulses = await cursor.to_list(length=None)
        
        results = []
        for p in my_pulses:
            results.append(await self.get_pulse_status(user_id, p["partner_id"]))
        return results

    async def check_aligned_connection(self, user_id: str, partner_id: str) -> Dict[str, Any]:
        """
        Specific API to check if both set 'Aligned' previously.
        If yes, and neither is aligned with anyone else, confirm connection.
        """
        status = await self.get_pulse_status(user_id, partner_id)
        
        if status["is_aligned_matched"]:
            return {
                "success": True,
                "is_aligned": True,
                "partner_id": partner_id,
                "partner_name": status["partner_name"],
                "message": f"You and {status['partner_name']} are mutually Aligned!"
            }
        
        return {
            "success": True,
            "is_aligned": False,
            "message": "You are not mutually Aligned with this partner yet."
        }

    async def delete_pulse(self, user_id: str, partner_id: str) -> bool:
        result = await self.pulses.delete_one({"user_id": user_id, "partner_id": partner_id})
        return result.deleted_count > 0

vibe_pulse_service = VibePulseService()
