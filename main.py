from fastapi import FastAPI
from app.routers import relationships, auth, checkin
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Include Routers
app.include_router(relationships.router)
app.include_router(auth.router)
app.include_router(checkin.router)


@app.get("/")
def root():
    return {"message": "loukarver API is running"}
