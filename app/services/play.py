from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.services.vibe_check import vibe_check_service
from app.services.vibe_card import vibe_card_service

class PlayService:
    def __init__(self) -> None:
        self.client = AsyncIOMotorClient(settings.MONGO_URL)
        self.db = self.client[settings.MONGO_DB_NAME]
        self.vibe_connections = self.db["vibe_check_connections"]
        self.cumulative_scores = self.db["vibe_cumulative_scores"]
        self.user_streaks = self.db["vibe_user_streaks"]

    async def get_play_stats(self, user_id: str) -> Dict[str, Any]:
        # 1. Get Viber Name
        profile = await vibe_check_service.get_profile(user_id)
        viber_name = profile["name"] if profile else "Unknown"

        # 2. Get Streak Days
        streak_info = await vibe_card_service.get_streak(user_id)
        streak_days = streak_info.get("current_streak", 0)

        # 3. Get Cumulated Match Percentage and Partner Name
        # Find the first partner from connections
        connection = await self.vibe_connections.find_one({"user_id": user_id})
        match_percentage = 0.0
        vibe_partner = "No Partner"
        
        if connection:
            partner_id = connection["partner_id"]
            
            # Fetch partner name
            partner_profile = await vibe_check_service.get_profile(partner_id)
            if partner_profile:
                vibe_partner = partner_profile["name"]

            score_doc = await self.cumulative_scores.find_one({
                "user_id": user_id, 
                "partner_id": partner_id
            })
            if score_doc:
                match_percentage = round(score_doc["score"], 1)

        return {
            "viber_name": viber_name,
            "vibe_partner": vibe_partner,
            "streak_days": streak_days,
            "cumulated_match_percentage": match_percentage
        }

play_service = PlayService()
