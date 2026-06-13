from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from app.core.config import settings
from app.schemas.checkin import CheckInCreate, CheckInUpdate

class CheckInService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.users_collection = self.db["users"]
        self.checkins_collection = self.db["check_ins"]

    async def get_checkin(self, user_id: str, date: str) -> Dict[str, Any]:
        """Gets checkin data for the user and their partner for a specific date."""
        # Get user to find partner
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise ValueError("User not found.")
            
        partner_id = None
        if user.get("is_aligned") and user.get("partner"):
            partner_id = user["partner"].get("user_id")
            
        my_check_in = await self.checkins_collection.find_one({"user_id": user_id, "date": date})
        partner_check_in = None
        is_partner_submit = False
        
        if partner_id:
            partner_check_in = await self.checkins_collection.find_one({"user_id": partner_id, "date": date})
            if partner_check_in:
                is_partner_submit = True
                
        # Format for response
        if my_check_in and "_id" in my_check_in:
            my_check_in["id"] = str(my_check_in["_id"])
            my_check_in["_id"] = str(my_check_in["_id"])
            
        if partner_check_in and "_id" in partner_check_in:
            partner_check_in["id"] = str(partner_check_in["_id"])
            partner_check_in["_id"] = str(partner_check_in["_id"])
            
        return {
            "is_partner_submit": is_partner_submit,
            "my_check_in": my_check_in,
            "partner_check_in": partner_check_in if is_partner_submit else None
        }

    async def create_checkin(self, user_id: str, payload: CheckInCreate) -> Dict[str, Any]:
        # Check if already exists for this date
        existing = await self.checkins_collection.find_one({"user_id": user_id, "date": payload.date})
        if existing:
            raise ValueError("You have already submitted a check-in for this date. Use PATCH to update.")
            
        new_checkin = {
            "user_id": user_id,
            "date": payload.date,
            "answer_1": payload.answer_1,
            "answer_2": payload.answer_2,
            "answer_3": payload.answer_3
        }
        
        result = await self.checkins_collection.insert_one(new_checkin)
        inserted = await self.checkins_collection.find_one({"_id": result.inserted_id})
        
        if inserted and "_id" in inserted:
            inserted["id"] = str(inserted["_id"])
            inserted["_id"] = str(inserted["_id"])
            
        return inserted

    async def update_checkin(self, user_id: str, payload: CheckInUpdate) -> Dict[str, Any]:
        existing = await self.checkins_collection.find_one({"user_id": user_id, "date": payload.date})
        if not existing:
            raise ValueError("No check-in found for this date. Use POST to create one.")
            
        updates = {}
        if payload.answer_1 is not None:
            updates["answer_1"] = payload.answer_1
        if payload.answer_2 is not None:
            updates["answer_2"] = payload.answer_2
        if payload.answer_3 is not None:
            updates["answer_3"] = payload.answer_3
            
        if not updates:
            raise ValueError("No fields provided to update.")
            
        await self.checkins_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": updates}
        )
        
        updated = await self.checkins_collection.find_one({"_id": existing["_id"]})
        if updated and "_id" in updated:
            updated["id"] = str(updated["_id"])
            updated["_id"] = str(updated["_id"])
            
        return updated

    async def get_questions(self) -> Dict[str, str]:
        """Returns the daily check-in questions."""
        return {
            "question_1": "How are you feeling?",
            "question_2": "What do you need most?",
            "question_3": "One thing on your mind..."
        }

checkin_service = CheckInService()
