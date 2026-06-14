import re
import zoneinfo
from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from app.core.config import settings
from app.schemas.lifecycle import PeriodCreate, PeriodUpdate, PhaseNoteCreate, PhaseNoteUpdate

def parse_date(date_str: str) -> date:
    """Parses mm.dd.yyyy or mm.dd,yyyy to date object."""
    parts = re.split(r"[\.,]", date_str)
    return date(int(parts[2]), int(parts[0]), int(parts[1]))

class LifeCycleService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.periods = self.db["period_history"]
        self.notes = self.db["lifecycle_notes"]
        self.users = self.db["users"]

    async def _get_owner_and_partner(self, user_id: str):
        """Returns the user ID of the woman in the relationship (the owner) and partner ID."""
        user = await self.users.find_one({"_id": ObjectId(user_id)})
        # For simplicity, we assume the person logging periods is the owner.
        # In a real app, we might check gender, but here we scope by the person who has period data.
        # If the current user has NO periods but their partner DOES, then the partner is the owner.
        
        has_periods = await self.periods.count_documents({"user_id": user_id})
        
        partner_id = None
        if user and user.get("is_aligned") and user.get("partner"):
            partner_id = user["partner"].get("user_id")
            
        if not has_periods and partner_id:
            partner_has_periods = await self.periods.count_documents({"user_id": partner_id})
            if partner_has_periods:
                return partner_id, user_id # Partner is the owner of the cycle
                
        return user_id, partner_id

    @staticmethod
    def _get_relative_time(created_at: datetime) -> str:
        """Returns a human-readable relative time string like '2 hours ago'."""
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        diff = now - created_at
        total_seconds = int(diff.total_seconds())

        if total_seconds < 0:
            return "just now"
        if total_seconds < 60:
            return "just now"
        
        minutes = total_seconds // 60
        if minutes < 60:
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        
        days = hours // 24
        if days < 7:
            return f"{days} day{'s' if days != 1 else ''} ago"
        
        weeks = days // 7
        if weeks < 4:
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        
        months = days // 30
        if months < 12:
            return f"{months} month{'s' if months != 1 else ''} ago"
        
        years = days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"

    async def get_cycle_stats(self, user_id: str) -> Dict[str, Any]:
        owner_id, partner_id = await self._get_owner_and_partner(user_id)
        
        # Fetch the period owner's name
        owner_user = await self.users.find_one({"_id": ObjectId(owner_id)})
        period_user_name = owner_user.get("name") if owner_user else None
        
        cursor = self.periods.find({"user_id": owner_id}).sort("start_date", -1)
        history = await cursor.to_list(length=10) # Last 10 periods for averaging
        
        if not history:
            return {
                "period_user_name": period_user_name,
                "stats": None,
                "history": [],
                "current_note": await self._get_current_note(owner_id, user_id, viewer_tz="UTC")
            }
            
        # 1. Calculate Average Cycle Length
        cycle_lengths = []
        parsed_history = []
        for i in range(len(history)):
            curr_date = parse_date(history[i]["start_date"])
            parsed_history.append({
                "id": str(history[i]["_id"]),
                "user_id": history[i]["user_id"],
                "start_date": history[i]["start_date"],
                "dt": curr_date
            })
            if i + 1 < len(history):
                prev_date = parse_date(history[i+1]["start_date"])
                diff = (curr_date - prev_date).days
                if 20 < diff < 45: # Filter out outliers
                    cycle_lengths.append(diff)
                    
        avg_cycle = int(sum(cycle_lengths) / len(cycle_lengths)) if cycle_lengths else 28
        
        # 2. Calculate Current Phase
        last_period = parsed_history[0]["dt"]
        today = date.today()
        days_since_start = (today - last_period).days
        
        # If it's been more than one full cycle, predict based on a new start
        # This handles cases where user forgot to log for months
        if days_since_start >= avg_cycle:
             # Just show Luteal/Late or reset to 0 relative to prediction
             days_in_current_cycle = days_since_start % avg_cycle
        else:
             days_in_current_cycle = days_since_start

        phase = ""
        description = ""
        if days_in_current_cycle < 5:
            phase = "Menstrual"
            description = "The period phase. Focus on rest and iron-rich foods."
        elif days_in_current_cycle < 13:
            phase = "Follicular"
            description = "Estrogen is rising. High energy and creativity."
        elif days_in_current_cycle < 16:
            phase = "Ovulatory"
            description = "Highest fertility. Peak communication and social energy."
        else:
            phase = "Luteal"
            description = "PMS may occur. Prioritize self-care and calming activities."

        next_period = last_period + timedelta(days=avg_cycle)
        while next_period <= today:
            next_period += timedelta(days=avg_cycle)
            
        days_left = (next_period - today).days

        stats = {
            "current_phase": phase,
            "days_since_start": days_since_start,
            "cycle_length_used": avg_cycle,
            "next_period_date": next_period.strftime("%m.%d.%Y"),
            "days_until_next_period": days_left,
            "phase_description": description
        }
        
        return {
            "period_user_name": period_user_name,
            "stats": stats,
            "history": [{"id": p["id"], "user_id": p["user_id"], "start_date": p["start_date"]} for p in parsed_history],
            "current_note": await self._get_current_note(owner_id, user_id, viewer_tz="UTC")
        }

    async def add_period(self, user_id: str, payload: PeriodCreate) -> Dict[str, Any]:
        new_period = {
            "user_id": user_id,
            "start_date": payload.start_date,
            "created_at": datetime.now(timezone.utc)
        }
        # Avoid duplicates for same date
        await self.periods.delete_many({"user_id": user_id, "start_date": payload.start_date})
        result = await self.periods.insert_one(new_period)
        
        # Ensure _id is a string and added as 'id'
        new_period["id"] = str(result.inserted_id)
        new_period["_id"] = str(result.inserted_id)
        return new_period

    async def update_period(self, user_id: str, period_id: str, payload: PeriodUpdate) -> Dict[str, Any]:
        result = await self.periods.update_one(
            {"_id": ObjectId(period_id), "user_id": user_id},
            {"$set": {"start_date": payload.start_date}}
        )
        if result.matched_count == 0:
            raise ValueError("Period record not found.")
        
        updated = await self.periods.find_one({"_id": ObjectId(period_id)})
        if updated:
            updated["id"] = str(updated["_id"])
            updated["_id"] = str(updated["_id"])
        return updated

    async def delete_period(self, user_id: str, period_id: str):
        await self.periods.delete_one({"_id": ObjectId(period_id), "user_id": user_id})

    # --- Phase Notes ---

    async def _get_current_note(self, owner_id: str, viewer_id: str, viewer_tz: str = "UTC") -> Optional[Dict[str, Any]]:
        """Gets the most recent note for today (based on viewer timezone)."""
        try:
            tz = zoneinfo.ZoneInfo(viewer_tz)
        except Exception:
            tz = zoneinfo.ZoneInfo("UTC")
        
        local_now = datetime.now(tz)
        today_str = local_now.strftime("%m.%d.%Y")
        
        note = await self.notes.find_one({"user_id": owner_id, "date": today_str})
        if note:
            created_at = note.get("created_at")
            created_ago = self._get_relative_time(created_at) if created_at else "unknown"
            return {
                "id": str(note["_id"]),
                "user_id": note["user_id"],
                "date": note["date"],
                "text": note["text"],
                "created_ago": created_ago,
                "is_owner": note["user_id"] == viewer_id
            }
        return None

    async def add_note(self, user_id: str, payload: PhaseNoteCreate) -> Dict[str, Any]:
        """Adds or updates a text note. Date is auto-resolved from the user's timezone."""
        try:
            tz = zoneinfo.ZoneInfo(payload.timezone)
        except Exception:
            raise ValueError(f"Invalid timezone: {payload.timezone}")
        
        local_now = datetime.now(tz)
        auto_date = local_now.strftime("%m.%d.%Y")
        now_utc = datetime.now(timezone.utc)

        new_note = {
            "user_id": user_id,
            "date": auto_date,
            "text": payload.text,
            "timezone": payload.timezone,
            "created_at": now_utc
        }
        # Upsert for specific date
        await self.notes.update_one(
            {"user_id": user_id, "date": auto_date},
            {"$set": new_note},
            upsert=True
        )
        doc = await self.notes.find_one({"user_id": user_id, "date": auto_date})
        created_at = doc.get("created_at")
        created_ago = self._get_relative_time(created_at) if created_at else "just now"
        return {
            "id": str(doc["_id"]),
            "user_id": doc["user_id"],
            "date": doc["date"],
            "text": doc["text"],
            "created_ago": created_ago,
            "is_owner": True
        }

    async def update_note(self, user_id: str, note_id: str, payload: PhaseNoteUpdate) -> Dict[str, Any]:
        result = await self.notes.update_one(
            {"_id": ObjectId(note_id), "user_id": user_id},
            {"$set": {"text": payload.text}}
        )
        if result.matched_count == 0:
            raise PermissionError("Note not found or you are not the owner.")
        return {"success": True}

    async def delete_note(self, user_id: str, note_id: str):
        result = await self.notes.delete_one({"_id": ObjectId(note_id), "user_id": user_id})
        if result.deleted_count == 0:
            raise PermissionError("Note not found or you are not the owner.")

lifecycle_service = LifeCycleService()
