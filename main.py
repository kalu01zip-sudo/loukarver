from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os
from app.routers import relationships, auth, checkin, rituals, streak, us, music, mood
from app.services.streak import streak_system
from app.services.mood import mood_service
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    await streak_system.init_indexes()
    await mood_service.seed_defaults()

# Include Routers
app.include_router(relationships.router)
app.include_router(auth.router)
app.include_router(checkin.router)
app.include_router(rituals.router)
app.include_router(streak.router)
app.include_router(us.router)
app.include_router(music.router)
app.include_router(mood.router)

# Mount StaticFiles for uploaded files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def root():
    return {"message": "loukarver API is running"}
