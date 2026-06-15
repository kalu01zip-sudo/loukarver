from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List

from app.routers.auth import get_current_user
from app.schemas.watch import (
    WatchSessionCreate, WatchSessionUpdate, WatchSessionRead,
    WatchSessionResponse, WatchSessionListResponse, GenericResponse
)
from app.services.watch import watch_service

router = APIRouter(prefix="/watch", tags=["Watch Together"])

@router.post("", response_model=WatchSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_watch_session(payload: WatchSessionCreate, current_user: dict = Depends(get_current_user)):
    """
    Schedule a new watch session with your partner.
    
    Example:
    ```json
    {
      "platform": "Youtube",
      "show_name": "Shakira, Burna Boy - Dai Dai (Official Video)",
      "link": "https://youtu.be/fcnDmrtj6Sk?si=ENZkfrEQZeGwI0Dt",
      "date": "06.15.2026",
      "time": "09:00 PM",
      "timezone": "Asia/Dhaka"
    }
    ```
    """
    try:
        result = await watch_service.create_session(current_user["id"], payload)
        return WatchSessionResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{session_id}/accept", response_model=WatchSessionResponse)
async def accept_watch_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Accept a watch session scheduled by your partner."""
    try:
        result = await watch_service.accept_session(session_id, current_user["id"])
        return WatchSessionResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=WatchSessionListResponse)
async def get_watch_sessions(current_user: dict = Depends(get_current_user)):
    """Get all watch sessions for the couple."""
    try:
        results = await watch_service.get_sessions(current_user["id"])
        return WatchSessionListResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}", response_model=WatchSessionResponse)
async def get_watch_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Get details of a specific watch session."""
    try:
        result = await watch_service.get_session(session_id, current_user["id"])
        if not result:
            raise HTTPException(status_code=404, detail="Watch session not found")
        return WatchSessionResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{session_id}", response_model=WatchSessionResponse)
async def update_watch_session(session_id: str, payload: WatchSessionUpdate, current_user: dict = Depends(get_current_user)):
    """Update a watch session's details."""
    try:
        result = await watch_service.update_session(session_id, current_user["id"], payload)
        if not result:
            raise HTTPException(status_code=404, detail="Watch session not found")
        return WatchSessionResponse(success=True, data=result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{session_id}", response_model=GenericResponse)
async def delete_watch_session(session_id: str, current_user: dict = Depends(get_current_user)):
    """Cancel and delete a watch session."""
    try:
        success = await watch_service.delete_session(session_id, current_user["id"])
        if not success:
            raise HTTPException(status_code=404, detail="Watch session not found")
        return GenericResponse(success=True, message="Watch session deleted")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{session_id}/ready", response_model=WatchSessionResponse)
async def set_ready(session_id: str, is_ready: bool = Query(True), current_user: dict = Depends(get_current_user)):
    """Signal that you are ready to start the show."""
    try:
        result = await watch_service.set_ready(session_id, current_user["id"], is_ready)
        return WatchSessionResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{session_id}/play", response_model=WatchSessionResponse)
async def trigger_play(session_id: str, current_user: dict = Depends(get_current_user)):
    """Trigger the 'Play' signal when both are ready."""
    try:
        result = await watch_service.trigger_play(session_id, current_user["id"])
        return WatchSessionResponse(success=True, data=result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
