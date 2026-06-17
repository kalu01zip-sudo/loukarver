from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from app.routers import (
    relationships, auth, checkin, rituals, streak, us, 
    music, mood, lifecycle, energy, ideas, interactions, watch, secret, dates, thread, milestone, map, notification, vibe_check, vibe_card, play, vibe_dates, vibe_pulse
)
from app.services.streak import streak_system
from app.services.mood import mood_service
from app.services.ideas import idea_service
from app.services.interactions import interaction_service
from app.services.secret import secret_service
from app.services.dates import date_service
from app.services.thread import thread_service
from app.services.milestone import milestone_service
from app.services.map import map_service
from app.services.notification import notification_service
from app.services.vibe_check import vibe_check_service
from app.services.vibe_card import vibe_card_service
from app.services.play import play_service
from app.services.vibe_dates import vibe_date_service
from app.services.vibe_pulse import vibe_pulse_service
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
)

@app.on_event("startup")
async def startup_event():
    await streak_system.init_indexes()
    await mood_service.seed_defaults()
    await idea_service.init_indexes()
    await idea_service.seed_defaults()
    await interaction_service.init_indexes()
    await secret_service.init_indexes()
    await date_service.init_indexes()
    await thread_service.init_indexes()
    await milestone_service.init_indexes()
    await map_service.init_indexes()
    await notification_service.init_indexes()
    await vibe_check_service.init_indexes()
    await vibe_card_service.init_indexes()
    await vibe_date_service.init_indexes()
    await vibe_pulse_service.init_indexes()

# Include Routers
app.include_router(relationships.router)
app.include_router(auth.router)
app.include_router(checkin.router)
app.include_router(rituals.router)
app.include_router(streak.router)
app.include_router(us.router)
app.include_router(music.router)
app.include_router(mood.router)
app.include_router(lifecycle.router)
app.include_router(energy.router)
app.include_router(ideas.router)
app.include_router(interactions.router)
app.include_router(watch.router)
app.include_router(secret.router)
app.include_router(dates.router)
app.include_router(thread.router)
app.include_router(milestone.router)
app.include_router(map.router)
app.include_router(notification.router)
app.include_router(vibe_check.router)
app.include_router(vibe_card.router)
app.include_router(play.router)
app.include_router(vibe_dates.router)
app.include_router(vibe_pulse.router)

# Mount StaticFiles for uploaded files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    return {"message": "loukarver API is running"}
