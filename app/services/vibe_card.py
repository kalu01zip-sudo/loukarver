import os
import json
import uuid
import zoneinfo
import httpx
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.schemas.vibe_card import VibeAnswerSubmit, VibeQuestion

class VibeCardService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.daily_pool = self.db["vibe_daily_pool"]
        self.user_answers = self.db["vibe_user_answers"]
        self.cumulative_scores = self.db["vibe_cumulative_scores"]
        self.vibe_profiles = self.db["vibe_check_profiles"]
        self.vibe_connections = self.db["vibe_check_connections"]
        self.user_streaks = self.db["vibe_user_streaks"]

    async def init_indexes(self):
        await self.daily_pool.create_index("date", unique=True)
        await self.user_answers.create_index([("user_id", 1), ("date", 1)], unique=True)
        await self.cumulative_scores.create_index([("user_id", 1), ("partner_id", 1)], unique=True)
        await self.user_streaks.create_index("user_id", unique=True)

    async def _generate_daily_pool(self) -> List[Dict[str, Any]]:
        """Uses Gemini to generate 12 'This or That' questions."""
        prompt = (
            "Generate 12 engaging 'This or That' questions for a social app. "
            "Format the output as a JSON list of objects, each with 'text', 'option_a', and 'option_b'. "
            "Questions should be fun, lighthearted, and occasionally deep (e.g. 'Beach or Mountain', 'Plan everything or Wing it')."
        )
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    questions = json.loads(raw_text)
                    
                    # Add IDs
                    for q in questions:
                        q["id"] = str(uuid.uuid4())
                    return questions
        except Exception as e:
            print(f"Gemini generation error: {e}")
        
        # Static Fallback if Gemini fails
        return [
            {"id": "f1", "text": "Weekend Vibes", "option_a": "City Break", "option_b": "Nature Escape"},
            {"id": "f2", "text": "Communication", "option_a": "Texting", "option_b": "Voice Notes"},
            {"id": "f3", "text": "Late Night", "option_a": "Movie Marathon", "option_b": "Deep Conversations"}
        ]

    async def get_daily_questions(self, user_id: str, user_timezone: str = "UTC") -> List[Dict[str, Any]]:
        """Get the daily 3 questions. Generates pool if not exists for today."""
        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except:
            tz = zoneinfo.ZoneInfo("UTC")
            
        today_str = datetime.now(tz).strftime("%m.%d.%Y")
        
        pool_doc = await self.daily_pool.find_one({"date": today_str})
        if not pool_doc:
            questions = await self._generate_daily_pool()
            pool_doc = {
                "date": today_str,
                "questions": questions,
                "created_at": datetime.now(timezone.utc)
            }
            try:
                await self.daily_pool.insert_one(pool_doc)
            except: # Concurrent insertion safety
                pool_doc = await self.daily_pool.find_one({"date": today_str})

        # Select same 3 questions for everyone today (e.g. first 3)
        return pool_doc["questions"][:3]

    async def submit_answers(self, user_id: str, payload: VibeAnswerSubmit) -> Dict[str, Any]:
        """Submit daily answers and update streak."""
        try:
            tz = zoneinfo.ZoneInfo(payload.timezone)
        except:
            tz = zoneinfo.ZoneInfo("UTC")
            
        now_local = datetime.now(tz)
        today_str = now_local.strftime("%m.%d.%Y")
        
        # 1. Save Answers
        answer_doc = {
            "user_id": user_id,
            "date": today_str,
            "answers": [a.model_dump() for a in payload.answers],
            "created_at": datetime.now(timezone.utc)
        }
        
        try:
            await self.user_answers.insert_one(answer_doc)
        except:
            raise ValueError("You have already answered today's questions.")

        # 2. Update Streak
        streak_doc = await self.user_streaks.find_one({"user_id": user_id})
        yesterday_str = (now_local - timedelta(days=1)).strftime("%m.%d.%Y")
        
        if not streak_doc:
            streak_doc = {"user_id": user_id, "current_streak": 1, "last_answered_date": today_str, "updated_at": datetime.now(timezone.utc)}
            await self.user_streaks.insert_one(streak_doc)
        else:
            if streak_doc["last_answered_date"] == yesterday_str:
                new_streak = streak_doc["current_streak"] + 1
            elif streak_doc["last_answered_date"] == today_str:
                new_streak = streak_doc["current_streak"]
            else:
                new_streak = 1
            
            await self.user_streaks.update_one(
                {"user_id": user_id},
                {"$set": {"current_streak": new_streak, "last_answered_date": today_str, "updated_at": datetime.now(timezone.utc)}}
            )

        return {"success": True, "message": "Answers submitted and streak updated!"}

    async def get_match_results(self, user_id: str, partner_id: str, user_timezone: str = "UTC") -> Dict[str, Any]:
        """Compare daily answers and calculate/update cumulative match score."""
        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except:
            tz = zoneinfo.ZoneInfo("UTC")
            
        today_str = datetime.now(tz).strftime("%m.%d.%Y")
        
        # 1. Fetch Profiles/Connections
        user_profile = await self.vibe_profiles.find_one({"user_id": user_id})
        partner_profile = await self.vibe_profiles.find_one({"user_id": partner_id})
        if not user_profile: raise ValueError("Your profile was not found.")
        if not partner_profile: raise ValueError("Partner not found.")
        
        is_connected = await self.vibe_connections.find_one({"user_id": user_id, "partner_id": partner_id})
        if not is_connected: raise ValueError("You are not connected with this user.")

        # 2. Fetch Answers
        my_ans = await self.user_answers.find_one({"user_id": user_id, "date": today_str})
        pa_ans = await self.user_answers.find_one({"user_id": partner_id, "date": today_str})
        
        if not my_ans: raise ValueError("You haven't answered today's questions yet.")
        if not pa_ans: raise ValueError("Partner hasn't answered today's questions yet.")

        # 3. Calculate Daily Match
        questions = await self.get_daily_questions(user_id, user_timezone)
        q_map = {q["id"]: q for q in questions}
        
        my_map = {a["question_id"]: a["selected_option"] for a in my_ans["answers"]}
        pa_map = {a["question_id"]: a["selected_option"] for a in pa_ans["answers"]}
        
        matches = 0
        total_q = len(questions)
        matched_details = []
        
        for qid, q in q_map.items():
            my_choice = my_map.get(qid)
            pa_choice = pa_map.get(qid)
            is_match = (my_choice == pa_choice)
            if is_match: matches += 1
            
            matched_details.append({
                "question": q["text"],
                "option_a": q["option_a"],
                "option_b": q["option_b"],
                "my_selected_option": my_choice,
                "partner_selected_option": pa_choice,
                "my_answer": q["option_a"] if my_choice == "A" else q["option_b"],
                "partner_answer": q["option_a"] if pa_choice == "A" else q["option_b"],
                "is_match": is_match
            })
            
        daily_match_percent = (matches / total_q * 100) if total_q > 0 else 0.0

        # 4. Handle Cumulative Score (EMA)
        score_doc = await self.cumulative_scores.find_one({"user_id": user_id, "partner_id": partner_id})
        
        if not score_doc:
            current_cumulative = 50.0 # Starting point
        else:
            current_cumulative = score_doc["score"]

        # Only update once per day per couple to prevent inflation
        last_updated = score_doc.get("last_updated_date") if score_doc else None
        
        if last_updated != today_str:
            # Formula: new = (old * 0.9) + (daily * 0.1)
            new_cumulative = (current_cumulative * 0.9) + (daily_match_percent * 0.1)
            await self.cumulative_scores.update_one(
                {"user_id": user_id, "partner_id": partner_id},
                {"$set": {"score": new_cumulative, "last_updated_date": today_str, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            # Mutual update
            await self.cumulative_scores.update_one(
                {"user_id": partner_id, "partner_id": user_id},
                {"$set": {"score": new_cumulative, "last_updated_date": today_str, "updated_at": datetime.now(timezone.utc)}},
                upsert=True
            )
            current_cumulative = new_cumulative

        return {
            "user_name": user_profile["name"],
            "partner_name": partner_profile["name"],
            "daily_match_percent": round(daily_match_percent, 1),
            "cumulative_match_percent": round(current_cumulative, 1),
            "matched_answers": matched_details
        }

    async def get_streak(self, user_id: str, user_timezone: str = "UTC") -> Dict[str, Any]:
        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except:
            tz = zoneinfo.ZoneInfo("UTC")
            
        today_str = datetime.now(tz).strftime("%m.%d.%Y")
        streak_doc = await self.user_streaks.find_one({"user_id": user_id})
        is_answered = await self.user_answers.find_one({"user_id": user_id, "date": today_str})
        
        if not streak_doc:
            return {"current_streak": 0, "last_answered": None, "is_answered_today": False}
            
        return {
            "current_streak": streak_doc["current_streak"],
            "last_answered": streak_doc["updated_at"],
            "is_answered_today": is_answered is not None
        }

vibe_card_service = VibeCardService()
