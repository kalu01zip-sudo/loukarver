from fastapi import APIRouter, Depends, HTTPException, status
from app.routers.auth import get_current_user
from app.schemas.mood import (
    MoodListCreate, MoodListUpdate, MoodListResponse,
    MoodLogCreate, MoodLogUpdate, MoodHistoryResponse,
    CurrentMoodResponse, GenericResponse
)
from app.services.mood import mood_service

router = APIRouter(prefix="/mood", tags=["Mood"])

# --- Mood List Endpoints ---

@router.get("/list", response_model=MoodListResponse, status_code=status.HTTP_200_OK)
async def get_mood_list(current_user: dict = Depends(get_current_user)):
    """Get the list of available moods to choose from."""
    try:
        results = await mood_service.get_mood_list(current_user["id"])
        return MoodListResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/list", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
async def create_mood_option(payload: MoodListCreate, current_user: dict = Depends(get_current_user)):
    """Create a new mood option."""
    try:
        await mood_service.create_mood_option(current_user["id"], payload)
        return GenericResponse(success=True, message="Mood option created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/list/{mood_id}", response_model=GenericResponse, status_code=status.HTTP_200_OK)
async def update_mood_option(mood_id: str, payload: MoodListUpdate, current_user: dict = Depends(get_current_user)):
    """Update an existing mood option."""
    try:
        await mood_service.update_mood_option(current_user["id"], mood_id, payload)
        return GenericResponse(success=True, message="Mood option updated.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/list/{mood_id}", response_model=GenericResponse, status_code=status.HTTP_200_OK)
async def delete_mood_option(mood_id: str, current_user: dict = Depends(get_current_user)):
    """Soft delete a mood option."""
    try:
        await mood_service.delete_mood_option(current_user["id"], mood_id)
        return GenericResponse(success=True, message="Mood option deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Mood Tracking Endpoints ---

@router.get("/current", response_model=CurrentMoodResponse, status_code=status.HTTP_200_OK)
async def get_current_mood(current_user: dict = Depends(get_current_user)):
    """Get the most recent mood state for both the user and their partner."""
    try:
        results = await mood_service.get_current_moods(current_user["id"])
        return CurrentMoodResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=MoodHistoryResponse, status_code=status.HTTP_200_OK)
async def get_mood_history(current_user: dict = Depends(get_current_user)):
    """Get a history of the user's logged moods."""
    try:
        results = await mood_service.get_mood_history(current_user["id"])
        return MoodHistoryResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
async def log_mood(payload: MoodLogCreate, current_user: dict = Depends(get_current_user)):
    """Log a new mood for the current user."""
    try:
        await mood_service.log_mood(current_user["id"], payload)
        return GenericResponse(success=True, message="Mood logged successfully.")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{log_id}", response_model=GenericResponse, status_code=status.HTTP_200_OK)
async def update_logged_mood(log_id: str, payload: MoodLogUpdate, current_user: dict = Depends(get_current_user)):
    """Update a previously logged mood entry."""
    try:
        await mood_service.update_logged_mood(log_id, current_user["id"], payload)
        return GenericResponse(success=True, message="Mood log updated.")
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{log_id}", response_model=GenericResponse, status_code=status.HTTP_200_OK)
async def delete_logged_mood(log_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a previously logged mood entry."""
    try:
        await mood_service.delete_logged_mood(log_id, current_user["id"])
        return GenericResponse(success=True, message="Mood log deleted.")
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
