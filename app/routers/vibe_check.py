from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.routers.auth import get_current_user
from app.schemas.vibe_check import (
    VibeCheckProfileCreate, VibeCheckProfileResponse, VibeCheckGenericResponse,
    VibeCheckConnectRequest, VibeCheckConnectionsResponse, VibeCheckRequestsResponse,
    VibeCheckRespondRequest, VibeInviteResponse, VibeInviteValidateResponse,
    VibeInviteAcceptRequest, VibeInviteAcceptResponse
)
from app.services.vibe_check import vibe_check_service

router = APIRouter(prefix="/vibecheck", tags=["VibeCheck"])

# --- Invite System ---

@router.post("/invite", response_model=VibeInviteResponse)
async def generate_vibecheck_invite(current_user: dict = Depends(get_current_user)):
    """Generate a unique invite link for VibeCheck."""
    try:
        return await vibe_check_service.generate_invite(current_user["id"])
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/invite/{invite_code}", response_model=VibeInviteValidateResponse)
async def validate_vibecheck_invite(invite_code: str):
    """Validate an invite code and return inviter info."""
    try:
        return await vibe_check_service.validate_invite(invite_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/invite/accept", response_model=VibeInviteAcceptResponse)
async def accept_vibecheck_invite(payload: VibeInviteAcceptRequest, current_user: dict = Depends(get_current_user)):
    """Accept an invite and connect with the inviter."""
    try:
        return await vibe_check_service.accept_invite(current_user["id"], payload.invite_code)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Existing Endpoints ---

@router.get("/profile", response_model=VibeCheckProfileResponse)
async def get_vibecheck_profile(current_user: dict = Depends(get_current_user)):
    """Get the user's VibeCheck profile."""
    profile = await vibe_check_service.get_profile(current_user["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="VibeCheck profile not setup yet.")
    return profile

@router.post("/setup", response_model=VibeCheckProfileResponse)
async def setup_vibecheck_profile(payload: VibeCheckProfileCreate, current_user: dict = Depends(get_current_user)):
    """Setup or update the user's VibeCheck profile."""
    try:
        return await vibe_check_service.create_or_update_profile(current_user["id"], payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/connect", response_model=VibeCheckGenericResponse)
async def connect_vibecheck(payload: VibeCheckConnectRequest, current_user: dict = Depends(get_current_user)):
    """Connect with another user using their Vibe Key."""
    try:
        return await vibe_check_service.connect_with_partner(current_user["id"], payload.vibe_key)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/connections", response_model=VibeCheckConnectionsResponse)
async def list_vibecheck_connections(current_user: dict = Depends(get_current_user)):
    """List all people you are connected with in VibeCheck."""
    try:
        connections = await vibe_check_service.get_connections(current_user["id"])
        return {"success": True, "data": connections}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/requests", response_model=VibeCheckRequestsResponse)
async def list_vibecheck_requests(current_user: dict = Depends(get_current_user)):
    """List all pending connection requests."""
    try:
        requests = await vibe_check_service.get_pending_requests(current_user["id"])
        return {"success": True, "data": requests}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/requests/{request_id}/respond", response_model=VibeCheckGenericResponse)
async def respond_vibecheck_request(
    request_id: str, 
    payload: VibeCheckRespondRequest, 
    current_user: dict = Depends(get_current_user)
):
    """Accept or reject a connection request."""
    try:
        return await vibe_check_service.respond_to_request(current_user["id"], request_id, payload.accept)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/connection/{partner_id}", response_model=VibeCheckGenericResponse)
async def delete_vibecheck_connection(partner_id: str, current_user: dict = Depends(get_current_user)):
    """Remove a connection from your VibeCheck network."""
    try:
        success = await vibe_check_service.delete_connection(current_user["id"], partner_id)
        if not success:
            raise HTTPException(status_code=404, detail="Connection not found.")
        return {"success": True, "message": "Connection removed successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/regenerate-key", response_model=VibeCheckGenericResponse)
async def regenerate_vibecheck_key(current_user: dict = Depends(get_current_user)):
    """Generate a new unique Vibe Key for your profile."""
    try:
        new_key = await vibe_check_service.regenerate_vibe_key(current_user["id"])
        return {"success": True, "message": f"New Vibe Key generated: {new_key}"}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/check", response_model=VibeCheckGenericResponse)
async def check_vibecheck_status(current_user: dict = Depends(get_current_user)):
    """Check if VibeCheck profile exists."""
    profile = await vibe_check_service.get_profile(current_user["id"])
    if profile:
        return {"success": True, "message": f"Profile exists for {profile['name']}"}
    return {"success": False, "message": "Profile not setup"}
