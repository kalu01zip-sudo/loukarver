from fastapi import APIRouter, Depends, HTTPException, status, Query
from app.routers.auth import get_current_user
from app.schemas.us import (
    UsResponse, UsStatsResponse, MilestoneCreate, MilestoneUpdate,
    NextMeetCreate, NextMeetUpdate, NextMeetResponse
)
from app.services.us import us_service

router = APIRouter(prefix="/us", tags=["Us"])

@router.get("", response_model=UsResponse, status_code=status.HTTP_200_OK)
async def get_us_stats(current_user: dict = Depends(get_current_user)):
    """
    Retrieves relationship statistics and milestones for the aligned couple.
    """
    try:
        stats = await us_service.get_stats(current_user["id"])
        if stats is None:
            return UsResponse(
                success=True,
                message="Alignment not completed yet. Start your journey together to see stats!",
                data=None
            )
            
        return UsResponse(
            success=True,
            message="Relationship stats retrieved successfully.",
            data=UsStatsResponse(**stats)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred fetching relationship stats: {str(e)}"
        )

# --- Milestone CRUD ---

@router.post("/milestones", status_code=status.HTTP_201_CREATED)
async def create_milestone(payload: MilestoneCreate, current_user: dict = Depends(get_current_user)):
    try:
        result = await us_service.create_milestone(current_user["id"], payload)
        return {
            "success": True,
            "message": "Milestone created successfully",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, payload: MilestoneUpdate, current_user: dict = Depends(get_current_user)):
    try:
        result = await us_service.update_milestone(current_user["id"], milestone_id, payload)
        return {
            "success": True,
            "message": "Milestone updated successfully",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/milestones/{milestone_id}")
async def delete_milestone(milestone_id: str, current_user: dict = Depends(get_current_user)):
    try:
        await us_service.delete_milestone(current_user["id"], milestone_id)
        return {
            "success": True,
            "message": "Milestone deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Next Meet CRUD & Countdown ---

@router.post("/next-meet", status_code=status.HTTP_201_CREATED)
async def set_next_meet(payload: NextMeetCreate, current_user: dict = Depends(get_current_user)):
    try:
        result = await us_service.set_next_meet(current_user["id"], payload)
        return {
            "success": True,
            "message": "Next meet set successfully",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/next-meet")
async def update_next_meet(payload: NextMeetUpdate, current_user: dict = Depends(get_current_user)):
    try:
        result = await us_service.update_next_meet(current_user["id"], payload)
        return {
            "success": True,
            "message": "Next meet updated successfully",
            "data": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/next-meet")
async def delete_next_meet(current_user: dict = Depends(get_current_user)):
    try:
        await us_service.delete_next_meet(current_user["id"])
        return {
            "success": True,
            "message": "Next meet deleted successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/next-meet/countdown", response_model=NextMeetResponse)
async def get_next_meet_countdown(viewer_timezone: str = Query("UTC", description="Your current IANA timezone (e.g. Asia/Dhaka)"), current_user: dict = Depends(get_current_user)):
    try:
        result = await us_service.get_next_meet_countdown(current_user["id"], viewer_timezone)
        if result is None:
            return NextMeetResponse(
                success=True,
                message="No upcoming meet found.",
                data=None
            )
        return NextMeetResponse(
            success=True,
            message="Countdown retrieved successfully.",
            data=result
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
