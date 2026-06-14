from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
from app.services.streak_algo import get_local_now, calculate_streak, is_at_risk
from app.schemas.ritual import RitualCompleteRequest

class StreakSystem:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.users_collection = self.db["users"]
        self.rituals_collection = self.db["ritual_completions"]

    async def init_indexes(self):
        await self.rituals_collection.create_index(
            [("user_id", 1), ("completed_date", 1)],
            unique=True
        )

    async def mark_ritual_complete(self, user_id: str, payload: RitualCompleteRequest) -> Dict[str, Any]:
        local_now = get_local_now(payload.timezone)
        date_str = local_now.strftime("%Y-%m-%d")
        
        already_completed_today = False
        new_doc = {
            "user_id": user_id,
            "completed_date": date_str,
            "ritual_type": payload.ritual_type.value,
            "text": payload.text,
            "created_at": datetime.utcnow()
        }
        try:
            await self.rituals_collection.insert_one(new_doc)
        except DuplicateKeyError:
            already_completed_today = True

        # Now recalculate streak
        current_streak, longest_streak = await self._recalculate_streak(user_id, date_str)
        
        return {
            "success": True,
            "already_completed_today": already_completed_today,
            "streak": current_streak,
            "message": "Ritual completed successfully" if not already_completed_today else "Ritual already completed today"
        }

    async def _recalculate_streak(self, user_id: str, target_date_str: str):
        # Fetch all dates
        cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        docs = await cursor.to_list(length=None)
        completed_dates = {doc["completed_date"] for doc in docs}
        
        streak = calculate_streak(completed_dates, target_date_str)
        
        # update user's streak cache
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        longest_streak = user.get("longest_streak", 0) if user else 0
        if streak > longest_streak:
            longest_streak = streak
            
        await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "current_streak": streak,
                "longest_streak": longest_streak,
                "last_completed_date": target_date_str,
                "updated_at": datetime.utcnow()
            }}
        )
        return streak, longest_streak

    async def get_current_streak(self, user_id: str, timezone: str) -> Dict[str, Any]:
        local_now = get_local_now(timezone)
        current_date_str = local_now.strftime("%Y-%m-%d")
        current_hour = local_now.hour
        
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        
        # We fetch dates again to accurately calculate is_at_risk and exact current streak 
        # (in case time has passed and current_streak cache is stale)
        cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        docs = await cursor.to_list(length=None)
        completed_dates = {doc["completed_date"] for doc in docs}
        
        current_streak = calculate_streak(completed_dates, current_date_str)
        risk = is_at_risk(completed_dates, current_date_str, current_hour)
        
        return {
            "current_streak": current_streak,
            "longest_streak": user.get("longest_streak", 0) if user else 0,
            "last_completed_date": user.get("last_completed_date") if user else None,
            "is_at_risk": risk
        }

    async def get_weekly_breakdown(self, user_id: str, timezone: str) -> Dict[str, Any]:
        from datetime import timedelta
        local_now = get_local_now(timezone)
        current_date = local_now.date()
        
        dates_to_check = []
        for i in range(7):
            d = current_date - timedelta(days=i)
            dates_to_check.append(d)
            
        dates_str = [d.strftime("%Y-%m-%d") for d in dates_to_check]
        
        cursor = self.rituals_collection.find({
            "user_id": user_id,
            "completed_date": {"$in": dates_str}
        })
        docs = await cursor.to_list(length=None)
        comp_map = {doc["completed_date"]: doc["ritual_type"] for doc in docs}
        
        days = []
        completed_count = 0
        for i, d in enumerate(dates_to_check):
            d_str = d.strftime("%Y-%m-%d")
            completed = d_str in comp_map
            if completed:
                completed_count += 1
                
            label = "Today" if i == 0 else ("Yesterday" if i == 1 else f"{i} days ago")
            days.append({
                "label": label,
                "date": d_str,
                "completed": completed,
                "ritual_type": comp_map.get(d_str)
            })
            
        return {
            "days": days,
            "week_completion_rate": int((completed_count / 7) * 100)
        }

    async def get_partner_streak(self, user_id: str, timezone: str) -> Dict[str, Any]:
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user or not user.get("partner"):
            return {
                "partner_name": "None",
                "partner_streak": 0,
                "partner_last_completed": None,
                "combined_days_both_completed": 0
            }
            
        partner_id = user["partner"]["user_id"]
        partner = await self.users_collection.find_one({"_id": ObjectId(partner_id)})
        
        # Combined days
        my_cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        my_docs = await my_cursor.to_list(length=None)
        my_dates = {doc["completed_date"] for doc in my_docs}
        
        partner_cursor = self.rituals_collection.find({"user_id": partner_id}, {"completed_date": 1})
        partner_docs = await partner_cursor.to_list(length=None)
        partner_dates = {doc["completed_date"] for doc in partner_docs}
        
        combined_days = len(my_dates.intersection(partner_dates))
        
        return {
            "partner_name": partner.get("name", "Unknown") if partner else "Unknown",
            "partner_streak": partner.get("current_streak", 0) if partner else 0,
            "partner_last_completed": partner.get("last_completed_date") if partner else None,
            "combined_days_both_completed": combined_days
        }

    async def get_history(self, user_id: str, page: int, limit: int, timezone: str) -> Dict[str, Any]:
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        partner_id = None
        partner_name = "Partner"
        user_name = user.get("name", "Me") if user else "Me"
        
        if user and user.get("partner"):
            partner_id = user["partner"]["user_id"]
            partner_name = user["partner"].get("name", "Partner")
            
        user_ids = [user_id]
        if partner_id:
            user_ids.append(partner_id)
            
        skip = (page - 1) * limit
        cursor = self.rituals_collection.find({"user_id": {"$in": user_ids}})\
            .sort([("completed_date", -1), ("created_at", -1)])\
            .skip(skip).limit(limit)
        docs = await cursor.to_list(length=None)
        
        total = await self.rituals_collection.count_documents({"user_id": {"$in": user_ids}})
        
        local_now = get_local_now(timezone)
        current_date_str = local_now.strftime("%Y-%m-%d")
        
        all_cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        all_docs = await all_cursor.to_list(length=None)
        completed_dates = {doc["completed_date"] for doc in all_docs}
        streak = calculate_streak(completed_dates, current_date_str)
        
        data = []
        for doc in docs:
            is_partner = doc["user_id"] != user_id
            author = partner_name if is_partner else user_name
            data.append({
                "date": doc["completed_date"],
                "ritual_type": doc["ritual_type"],
                "completed": True,
                "text": doc.get("text"),
                "author_name": author,
                "is_partner": is_partner
            })
            
        return {
            "data": data,
            "total": total,
            "streak": streak
        }

    async def get_debug_history(self, user_id: str) -> List[str]:
        cursor = self.rituals_collection.find({"user_id": user_id}).sort("completed_date", 1)
        docs = await cursor.to_list(length=None)
        return [doc["completed_date"] for doc in docs]

streak_system = StreakSystem()
