from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone
import os
import uuid
from fastapi import UploadFile
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
from app.services.streak_algo import get_local_now, calculate_streak, is_at_risk
from app.schemas.ritual import RitualCompleteRequest

def get_time_name(hour: int) -> str:
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 21:
        return "evening"
    else:
        return "night"

class StreakSystem:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.users_collection = self.db["users"]
        self.rituals_collection = self.db["ritual_completions"]

    async def init_indexes(self):
        try:
            await self.rituals_collection.drop_index("user_id_1_completed_date_1")
        except Exception:
            pass
        await self.rituals_collection.create_index(
            [("user_id", 1), ("completed_date", 1)]
        )

    async def mark_ritual_complete(self, user_id: str, payload: RitualCompleteRequest, file: Optional[UploadFile] = None) -> Dict[str, Any]:
        local_now = get_local_now(payload.timezone)
        date_str = local_now.strftime("%Y-%m-%d")
        
        # Use provided time/time_name or generate them
        time_str = payload.time if payload.time else local_now.strftime("%I:%M %p")
        time_name = payload.time_name if payload.time_name else get_time_name(local_now.hour)
        
        # Check if a ritual has already been completed today
        existing_doc = await self.rituals_collection.find_one({
            "user_id": user_id,
            "completed_date": date_str
        })
        already_completed_today = existing_doc is not None
        
        # Handle file upload if provided
        file_path = None
        if file and file.filename:
            os.makedirs("uploads", exist_ok=True)
            ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            local_path = os.path.join("uploads", unique_filename)
            
            content = await file.read()
            with open(local_path, "wb") as f:
                f.write(content)
                
            file_path = f"/uploads/{unique_filename}"
        
        new_doc = {
            "user_id": user_id,
            "completed_date": date_str,
            "ritual_type": payload.ritual_type.value,
            "text": payload.text,
            "file_path": file_path,
            "time": time_str,
            "time_name": time_name,
            "created_at": datetime.now(timezone.utc)
        }
        result = await self.rituals_collection.insert_one(new_doc)
        ritual_id = str(result.inserted_id)

        # Now recalculate streak
        current_streak, longest_streak = await self._recalculate_streak(user_id, date_str)
        
        return {
            "success": True,
            "already_completed_today": already_completed_today,
            "streak": current_streak,
            "file_path": file_path,
            "ritual_id": ritual_id,
            "time": time_str,
            "time_name": time_name,
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
                "updated_at": datetime.now(timezone.utc)
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
        current_date_str = local_now.strftime("%Y-%m-%d")
        
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
        
        from collections import defaultdict
        comp_map = defaultdict(list)
        for doc in docs:
            comp_map[doc["completed_date"]].append(doc)
            
        days = []
        completed_count = 0
        for i, d in enumerate(dates_to_check):
            d_str = d.strftime("%Y-%m-%d")
            day_rituals = comp_map.get(d_str, [])
            completed = len(day_rituals) > 0
            
            if completed:
                completed_count += 1
                
            label = "Today" if i == 0 else ("Yesterday" if i == 1 else f"{i} days ago")
            
            # Primary ritual (first one)
            primary = day_rituals[0] if day_rituals else None
            
            ritual_data = []
            for r in day_rituals:
                ritual_data.append({
                    "ritual_type": r["ritual_type"],
                    "text": r.get("text"),
                    "file_path": r.get("file_path"),
                    "time": r.get("time"),
                    "time_name": r.get("time_name")
                })

            days.append({
                "label": label,
                "date": d_str,
                "completed": completed,
                "ritual_type": primary["ritual_type"] if primary else None,
                "time": primary.get("time") if primary else None,
                "time_name": primary.get("time_name") if primary else None,
                "data": ritual_data
            })
            
        # Get current streak
        user_cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        all_docs = await user_cursor.to_list(length=None)
        completed_dates = {doc["completed_date"] for doc in all_docs}
        current_streak = calculate_streak(completed_dates, current_date_str)

        return {
            "days": days,
            "week_completion_rate": int((completed_count / 7) * 100),
            "current_streak": current_streak
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
        actual_partner_name = partner_name if partner_id else None
        
        for doc in docs:
            is_partner = doc["user_id"] != user_id
            author = partner_name if is_partner else user_name
            current_partner = user_name if is_partner else actual_partner_name
            data.append({
                "ritual_id": str(doc["_id"]),
                "date": doc["completed_date"],
                "ritual_type": doc["ritual_type"],
                "completed": True,
                "text": doc.get("text"),
                "file_path": doc.get("file_path"),
                "author_name": author,
                "is_partner": is_partner,
                "partner_name": current_partner,
                "time": doc.get("time"),
                "time_name": doc.get("time_name")
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

    async def _update_streak_after_mutation(self, user_id: str, timezone: str = "UTC") -> int:
        local_now = get_local_now(timezone)
        current_date_str = local_now.strftime("%Y-%m-%d")
        
        cursor = self.rituals_collection.find({"user_id": user_id}, {"completed_date": 1})
        docs = await cursor.to_list(length=None)
        completed_dates = {doc["completed_date"] for doc in docs}
        
        streak = calculate_streak(completed_dates, current_date_str)
        
        user = await self.users_collection.find_one({"_id": ObjectId(user_id)})
        longest_streak = user.get("longest_streak", 0) if user else 0
        if streak > longest_streak:
            longest_streak = streak
            
        # Find the latest completed date from the remaining docs
        last_completed_date = None
        if completed_dates:
            last_completed_date = max(completed_dates)
            
        await self.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "current_streak": streak,
                "longest_streak": longest_streak,
                "last_completed_date": last_completed_date,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return streak

    async def update_ritual(
        self,
        user_id: str,
        ritual_id: str,
        ritual_type: Optional[str] = None,
        text: Optional[str] = None,
        file: Optional[UploadFile] = None,
        clear_file: bool = False,
        timezone: str = "UTC",
        time: Optional[str] = None,
        time_name: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            ritual_oid = ObjectId(ritual_id)
        except Exception:
            raise ValueError("Invalid ritual ID format")

        doc = await self.rituals_collection.find_one({"_id": ritual_oid})
        if not doc:
            raise ValueError("Ritual not found")
        if doc["user_id"] != user_id:
            raise PermissionError("You do not have permission to update this ritual")

        # Recalculate time and time_name based on creation time and current timezone if not provided
        if not time or not time_name:
            created_at = doc.get("created_at") or datetime.now(timezone.utc)
            import zoneinfo
            try:
                tz = zoneinfo.ZoneInfo(timezone)
                local_dt = created_at.replace(tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(tz)
            except Exception:
                local_dt = created_at.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
            
            if not time:
                time = local_dt.strftime("%I:%M %p")
            if not time_name:
                time_name = get_time_name(local_dt.hour)

        updates = {}
        if ritual_type is not None:
            updates["ritual_type"] = ritual_type
        if text is not None:
            updates["text"] = text
        updates["time"] = time
        updates["time_name"] = time_name


        file_path = doc.get("file_path")

        if clear_file:
            if file_path:
                local_path = file_path.lstrip("/")
                if os.path.exists(local_path):
                    os.remove(local_path)
                file_path = None
                updates["file_path"] = None
        elif file and file.filename:
            # Delete old file if exists
            if file_path:
                local_path = file_path.lstrip("/")
                if os.path.exists(local_path):
                    os.remove(local_path)
            
            os.makedirs("uploads", exist_ok=True)
            ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4().hex}{ext}"
            local_path = os.path.join("uploads", unique_filename)
            
            content = await file.read()
            with open(local_path, "wb") as f:
                f.write(content)
                
            file_path = f"/uploads/{unique_filename}"
            updates["file_path"] = file_path

        if updates:
            await self.rituals_collection.update_one({"_id": ritual_oid}, {"$set": updates})

        # Recalculate streak
        streak = await self._update_streak_after_mutation(user_id, timezone)

        return {
            "success": True,
            "message": "Ritual updated successfully",
            "ritual_id": ritual_id,
            "file_path": file_path,
            "streak": streak,
            "time": time,
            "time_name": time_name
        }

    async def delete_ritual(self, user_id: str, ritual_id: str, timezone: str = "UTC") -> Dict[str, Any]:
        try:
            ritual_oid = ObjectId(ritual_id)
        except Exception:
            raise ValueError("Invalid ritual ID format")

        doc = await self.rituals_collection.find_one({"_id": ritual_oid})
        if not doc:
            raise ValueError("Ritual not found")
        if doc["user_id"] != user_id:
            raise PermissionError("You do not have permission to delete this ritual")

        # Delete from disk
        file_path = doc.get("file_path")
        if file_path:
            local_path = file_path.lstrip("/")
            if os.path.exists(local_path):
                os.remove(local_path)

        await self.rituals_collection.delete_one({"_id": ritual_oid})

        # Recalculate streak
        streak = await self._update_streak_after_mutation(user_id, timezone)

        return {
            "success": True,
            "message": "Ritual deleted successfully",
            "streak": streak
        }

streak_system = StreakSystem()
