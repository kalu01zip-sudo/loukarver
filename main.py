from fastapi import FastAPI
from app.routers import relationships, auth, checkin, rituals, streak
from app.services.streak import streak_system
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

# Include Routers
app.include_router(relationships.router)
app.include_router(auth.router)
app.include_router(checkin.router)
app.include_router(rituals.router)
app.include_router(streak.router)

@app.get("/")
def root():
    return {"message": "loukarver API is running"}
