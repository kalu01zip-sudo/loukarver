from pydantic import BaseModel

class PlayStatsResponse(BaseModel):
    viber_name: str
    vibe_partner: str
    streak_days: int
    cumulated_match_percentage: float
