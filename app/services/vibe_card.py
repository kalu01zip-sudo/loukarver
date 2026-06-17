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
            "Format the output as a JSON list of objects, each with 'text', 'option_a', 'option_b', and 'category'. "
            "Categories should be things like 'Travel', 'Communication', 'Lifestyle', 'Emotional', 'Social', 'Values', etc. "
            "Questions should be fun, lighthearted, and occasionally deep (e.g. 'Beach or Mountain', 'Plan everything or Wing it')."
        )
        
        # Use gemini-3.5-flash for 2026 compatibility
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key={settings.GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    
                    # Robust parsing for JSON
                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                        
                    questions = json.loads(raw_text)
                    
                    # Add IDs
                    for q in questions:
                        q["id"] = str(uuid.uuid4())
                    return questions
                else:
                    print(f"Gemini API Error: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Gemini generation error: {e}")
        
        # Static Fallback if Gemini fails (diverse enough for some variety)
        return [
            {"id": "f1", "text": "Weekend Vibes", "option_a": "City Break", "option_b": "Nature Escape", "category": "Travel"},
            {"id": "f2", "text": "Communication", "option_a": "Texting", "option_b": "Voice Notes", "category": "Communication"},
            {"id": "f3", "text": "Late Night", "option_a": "Movie Marathon", "option_b": "Deep Conversations", "category": "Lifestyle"},
            {"id": "f4", "text": "Adventure", "option_a": "Skydiving", "option_b": "Scuba Diving", "category": "Social"},
            {"id": "f5", "text": "Social Life", "option_a": "Big Party", "option_b": "Small Gathering", "category": "Social"},
            {"id": "f6", "text": "Work Style", "option_a": "Early Bird", "option_b": "Night Owl", "category": "Lifestyle"},
            {"id": "f7", "text": "Cuisine", "option_a": "Spicy", "option_b": "Sweet", "category": "Lifestyle"},
            {"id": "f8", "text": "Travel", "option_a": "Solo Trip", "option_b": "Group Trip", "category": "Travel"},
            {"id": "f9", "text": "Entertainment", "option_a": "Reading", "option_b": "Gaming", "category": "Lifestyle"},
            {"id": "f10", "text": "Season", "option_a": "Summer", "option_b": "Winter", "category": "Travel"},
            {"id": "f11", "text": "Morning", "option_a": "Coffee", "option_b": "Tea", "category": "Lifestyle"},
            {"id": "f12", "text": "Habit", "option_a": "Journaling", "option_b": "Meditation", "category": "Emotional"}
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

        # Select 3 questions for everyone today. 
        # We use the day of the year to rotate through the 12 questions in the pool.
        # This ensures variety even if the pool isn't regenerated frequently.
        questions_pool = pool_doc["questions"]
        if not questions_pool:
            return []
            
        day_of_year = datetime.now(tz).timetuple().tm_yday
        start_idx = (day_of_year % (len(questions_pool) // 3)) * 3
        
        # Ensure start_idx is valid
        if start_idx + 3 > len(questions_pool):
            start_idx = 0
            
        return questions_pool[start_idx : start_idx + 3]

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

    async def get_match_results(self, user_id: str, partner_id: Optional[str] = None, user_timezone: str = "UTC") -> List[Dict[str, Any]]:
        """Compare daily answers and calculate/update cumulative match score for one or all partners."""
        try:
            tz = zoneinfo.ZoneInfo(user_timezone)
        except:
            tz = zoneinfo.ZoneInfo("UTC")
            
        today_str = datetime.now(tz).strftime("%m.%d.%Y")
        
        # 1. Fetch User Profile
        user_profile = await self.vibe_profiles.find_one({"user_id": user_id})
        if not user_profile: raise ValueError("Your profile was not found.")
        user_name = user_profile["name"]

        # 2. Identify Partners
        if partner_id:
            partner_ids = [partner_id]
        else:
            cursor = self.vibe_connections.find({"user_id": user_id}, {"partner_id": 1})
            conn_docs = await cursor.to_list(length=None)
            partner_ids = [c["partner_id"] for c in conn_docs]

        if not partner_ids:
            return []

        # 3. Fetch My Answers for Today
        my_ans = await self.user_answers.find_one({"user_id": user_id, "date": today_str})
        if not my_ans: 
            # If I haven't answered, I can't see any results
            return []

        questions = await self.get_daily_questions(user_id, user_timezone)
        q_map = {q["id"]: q for q in questions}
        my_map = {a["question_id"]: a["selected_option"] for a in my_ans["answers"]}
        
        results = []

        # 4. Process each partner
        for p_id in partner_ids:
            partner_profile = await self.vibe_profiles.find_one({"user_id": p_id})
            if not partner_profile: continue
            
            pa_ans = await self.user_answers.find_one({"user_id": p_id, "date": today_str})
            if not pa_ans: continue # Partner hasn't answered today

            pa_map = {a["question_id"]: a["selected_option"] for a in pa_ans["answers"]}
            
            matches = 0
            total_q = len(questions)
            matched_details = []
            
            for qid, q in q_map.items():
                my_choice = my_map.get(qid)
                pa_choice = pa_map.get(qid)
                if my_choice is None or pa_choice is None: continue
                
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

            # Handle Cumulative Score (EMA)
            score_doc = await self.cumulative_scores.find_one({"user_id": user_id, "partner_id": p_id})
            current_cumulative = score_doc["score"] if score_doc else 50.0
            last_updated = score_doc.get("last_updated_date") if score_doc else None
            
            if last_updated != today_str:
                new_cumulative = (current_cumulative * 0.9) + (daily_match_percent * 0.1)
                # Update both sides
                await self.cumulative_scores.update_one(
                    {"user_id": user_id, "partner_id": p_id},
                    {"$set": {"score": new_cumulative, "last_updated_date": today_str, "updated_at": datetime.now(timezone.utc)}},
                    upsert=True
                )
                await self.cumulative_scores.update_one(
                    {"user_id": p_id, "partner_id": user_id},
                    {"$set": {"score": new_cumulative, "last_updated_date": today_str, "updated_at": datetime.now(timezone.utc)}},
                    upsert=True
                )
                current_cumulative = new_cumulative

            results.append({
                "user_name": user_name,
                "partner_name": partner_profile["name"],
                "daily_match_percent": round(daily_match_percent, 1),
                "cumulative_match_percent": round(current_cumulative, 1),
                "matched_answers": matched_details
            })

        return results

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

    async def get_history(self, user_id: str, partner_id: Optional[str] = None, category: str = "All", page: int = 1, size: int = 20) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch answer history between user and partners with filtering and pagination."""
        # 1. Fetch User Profile
        user_profile = await self.vibe_profiles.find_one({"user_id": user_id})
        if not user_profile:
            return [], 0
        user_name = user_profile["name"]

        # 2. Identify Partners
        if partner_id:
            partner_ids = [partner_id]
        else:
            cursor = self.vibe_connections.find({"user_id": user_id}, {"partner_id": 1})
            conn_docs = await cursor.to_list(length=None)
            partner_ids = [c["partner_id"] for c in conn_docs]

        if not partner_ids:
            return [], 0

        # Fetch Partner Profiles
        partner_profiles_cursor = self.vibe_profiles.find({"user_id": {"$in": partner_ids}})
        partner_profiles_docs = await partner_profiles_cursor.to_list(length=None)
        partner_map = {p["user_id"]: p["name"] for p in partner_profiles_docs}

        # 3. Aggregate history for all partners
        history = []
        my_dates = await self.user_answers.distinct("date", {"user_id": user_id})
        pool_cache = {}

        for p_id in partner_ids:
            p_name = partner_map.get(p_id, "Unknown Partner")
            pa_dates = await self.user_answers.distinct("date", {"user_id": p_id})
            common_dates = list(set(my_dates) & set(pa_dates))
            
            for date_str in common_dates:
                if date_str not in pool_cache:
                    pool_cache[date_str] = await self.daily_pool.find_one({"date": date_str})
                
                pool = pool_cache[date_str]
                if not pool: continue
                
                my_ans = await self.user_answers.find_one({"user_id": user_id, "date": date_str})
                pa_ans = await self.user_answers.find_one({"user_id": p_id, "date": date_str})
                
                q_map = {q["id"]: q for q in pool["questions"]}
                my_map = {a["question_id"]: a["selected_option"] for a in my_ans["answers"]}
                pa_map = {a["question_id"]: a["selected_option"] for a in pa_ans["answers"]}
                
                for qid in list(my_map.keys() & pa_map.keys()):
                    q = q_map.get(qid)
                    if not q: continue
                    
                    my_choice = my_map[qid]
                    pa_choice = pa_map[qid]
                    is_match = (my_choice == pa_choice)
                    
                    # Apply Category Filter
                    if category == "Matched" and not is_match: continue
                    if category == "Differed" and is_match: continue
                    
                    history.append({
                        "date": date_str,
                        "question": q["text"],
                        "category": q.get("category", "General"),
                        "option_a": q["option_a"],
                        "option_b": q["option_b"],
                        "user_name": user_name,
                        "user_answer": q["option_a"] if my_choice == "A" else q["option_b"],
                        "partner_name": p_name,
                        "partner_answer": q["option_a"] if pa_choice == "A" else q["option_b"],
                        "is_match": is_match
                    })

        # 4. Sort and Paginate
        history.sort(reverse=True, key=lambda x: datetime.strptime(x["date"], "%m.%d.%Y"))
        
        total = len(history)
        skip = (page - 1) * size
        return history[skip : skip + size], total

    async def get_pulse_analytics(self, user_id: str, partner_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Provides detailed matching analytics across all partners or a specific one."""
        # 1. Identify Partners
        if partner_id:
            partner_ids = [partner_id]
        else:
            cursor = self.vibe_connections.find({"user_id": user_id}, {"partner_id": 1})
            conn_docs = await cursor.to_list(length=None)
            partner_ids = [c["partner_id"] for c in conn_docs]

        if not partner_ids:
            return []

        # 2. Fetch Partner Profiles
        partner_profiles_cursor = self.vibe_profiles.find({"user_id": {"$in": partner_ids}})
        partner_profiles_docs = await partner_profiles_cursor.to_list(length=None)
        partner_map = {p["user_id"]: p["name"] for p in partner_profiles_docs}

        analytics_results = []
        my_ans_cursor = self.user_answers.find({"user_id": user_id})
        my_all_answers = await my_ans_cursor.to_list(length=None)
        my_dates_map = {a["date"]: a for a in my_all_answers}

        pool_cache = {}

        for p_id in partner_ids:
            p_name = partner_map.get(p_id, "Unknown Partner")
            
            # Fetch partner's answers
            pa_ans_cursor = self.user_answers.find({"user_id": p_id})
            pa_all_answers = await pa_ans_cursor.to_list(length=None)
            
            common_dates = []
            for pa_doc in pa_all_answers:
                if pa_doc["date"] in my_dates_map:
                    common_dates.append(pa_doc["date"])
            
            category_stats = {} # {category: {total: X, match: Y}}
            all_history = []
            
            for date_str in common_dates:
                if date_str not in pool_cache:
                    pool_cache[date_str] = await self.daily_pool.find_one({"date": date_str})
                
                pool = pool_cache[date_str]
                if not pool: continue
                
                my_ans = my_dates_map[date_str]
                pa_ans = next(a for a in pa_all_answers if a["date"] == date_str)
                
                q_map = {q["id"]: q for q in pool["questions"]}
                my_ans_map = {a["question_id"]: a["selected_option"] for a in my_ans["answers"]}
                pa_ans_map = {a["question_id"]: a["selected_option"] for a in pa_ans["answers"]}
                
                for qid in list(my_ans_map.keys() & pa_ans_map.keys()):
                    q = q_map.get(qid)
                    if not q: continue
                    
                    cat = q.get("category", "General")
                    if cat not in category_stats:
                        category_stats[cat] = {"total": 0, "match": 0}
                    
                    my_choice = my_ans_map[qid]
                    pa_choice = pa_ans_map[qid]
                    is_match = (my_choice == pa_choice)
                    
                    category_stats[cat]["total"] += 1
                    if is_match:
                        category_stats[cat]["match"] += 1
                    
                    all_history.append({
                        "date": date_str,
                        "question": q["text"],
                        "category": cat,
                        "option_a": q["option_a"],
                        "option_b": q["option_b"],
                        "user_name": "Me",
                        "user_answer": q["option_a"] if my_choice == "A" else q["option_b"],
                        "partner_name": p_name,
                        "partner_answer": q["option_a"] if pa_choice == "A" else q["option_b"],
                        "is_match": is_match
                    })

            # Sort history by date
            all_history.sort(reverse=True, key=lambda x: datetime.strptime(x["date"], "%m.%d.%Y"))
            
            recent_matches = [h for h in all_history if h["is_match"]][:5]
            recent_differences = [h for h in all_history if not h["is_match"]][:5]
            
            # Calculate category matches
            cat_list = []
            for cat, s in category_stats.items():
                percent = (s["match"] / s["total"] * 100) if s["total"] > 0 else 0
                cat_list.append({
                    "category": cat,
                    "match_percentage": round(percent, 1),
                    "total_questions": s["total"],
                    "matched_questions": s["match"]
                })
            
            cat_list.sort(key=lambda x: x["match_percentage"], reverse=True)
            strongest = [c for c in cat_list if c["match_percentage"] >= 50][:3]
            weakest = [c for c in cat_list if c["match_percentage"] < 50][:3]
            # If strongest is empty, just take top 3
            if not strongest: strongest = cat_list[:3]
            # If weakest is empty, take bottom 3
            if not weakest: weakest = cat_list[-3:] if len(cat_list) > 3 else []

            total_q = sum(s["total"] for s in category_stats.values())
            total_m = sum(s["match"] for s in category_stats.values())
            overall_percent = (total_m / total_q * 100) if total_q > 0 else 0.0

            # Get cumulative score
            score_doc = await self.cumulative_scores.find_one({"user_id": user_id, "partner_id": p_id})
            cumulative = score_doc["score"] if score_doc else 50.0

            analytics_results.append({
                "partner_id": p_id,
                "partner_name": p_name,
                "cumulative_match_percent": round(cumulative, 1),
                "total_questions_answered": total_q,
                "matched_questions_count": total_m,
                "overall_match_percentage": round(overall_percent, 1),
                "strongest_categories": strongest,
                "weakest_categories": weakest,
                "recent_matches": recent_matches,
                "recent_differences": recent_differences
            })

        return analytics_results

vibe_card_service = VibeCardService()
