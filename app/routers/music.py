from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.routers.auth import get_current_user
from app.schemas.music import SearchResponse, AddTrackRequest, AddTrackResponse, PlaylistResponse
from app.services.youtube import youtube_service

router = APIRouter(prefix="/music", tags=["Music"])

@router.get("/youtube/login")
async def youtube_login(current_user: dict = Depends(get_current_user)):
    """Get the Google OAuth URL to link a YouTube account."""
    url = youtube_service.get_auth_url()
    return {"url": url}

@router.get("/youtube/callback")
async def youtube_callback(code: str, state: str = None, current_user: dict = Depends(get_current_user)):
    """Exchange the Google OAuth code for tokens and link the account."""
    try:
        await youtube_service.exchange_code(current_user["id"], code)
        return {"success": True, "message": "YouTube account linked successfully and playlist created."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search", response_model=SearchResponse, status_code=status.HTTP_200_OK)
async def search_music(q: str = Query(..., description="The search query"), current_user: dict = Depends(get_current_user)):
    """Search for music on YouTube."""
    try:
        results = await youtube_service.search_tracks(q)
        return SearchResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/playlist/add", response_model=AddTrackResponse, status_code=status.HTTP_200_OK)
async def add_track_to_playlist(payload: AddTrackRequest, current_user: dict = Depends(get_current_user)):
    """Add a track to the shared DB playlist and sync to linked YouTube playlists."""
    try:
        await youtube_service.add_track(
            user_id=current_user["id"],
            track_id=payload.id,
            title=payload.title,
            artist=payload.artist,
            cover_url=payload.cover_url
        )
        return AddTrackResponse(success=True, message="Track added and synced successfully.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlist", response_model=PlaylistResponse, status_code=status.HTTP_200_OK)
async def get_playlist(current_user: dict = Depends(get_current_user)):
    """Get the combined shared playlist for the user and their partner."""
    try:
        results = await youtube_service.get_shared_playlist(current_user["id"])
        return PlaylistResponse(success=True, data=results)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
