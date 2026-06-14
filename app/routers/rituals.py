from fastapi import APIRouter, Depends, HTTPException, status, Query, Form, File, UploadFile
from typing import Optional
from app.routers.auth import get_current_user
from app.schemas.ritual import (
    RitualCompleteRequest,
    RitualCompleteResponse,
    RitualHistoryResponse,
    RitualType,
    RitualUpdateResponse,
    RitualDeleteResponse
)
from app.services.streak import streak_system

router = APIRouter(prefix="/rituals", tags=["Rituals"])

@router.post("/complete", response_model=RitualCompleteResponse, status_code=status.HTTP_200_OK)
async def complete_ritual(
    ritual_type: RitualType = Form(..., description="The type of ritual completed"),
    timezone: str = Form("UTC", description="Client's timezone, e.g. America/Los_Angeles"),
    text: Optional[str] = Form(None, description="Optional text submission for the ritual"),
    file: Optional[UploadFile] = File(None, description="Optional file upload for the ritual"),
    time: Optional[str] = Form(None, description="Time of completion in 12h format"),
    time_name: Optional[str] = Form(None, description="Time name"),
    current_user: dict = Depends(get_current_user)
):
    try:
        payload = RitualCompleteRequest(
            ritual_type=ritual_type,
            timezone=timezone,
            text=text,
            time=time,
            time_name=time_name
        )
        result = await streak_system.mark_ritual_complete(current_user["id"], payload, file)
        return RitualCompleteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history", response_model=RitualHistoryResponse, status_code=status.HTTP_200_OK)
async def get_history(page: int = Query(1, ge=1), limit: int = Query(30, ge=1), timezone: str = Query("UTC"), current_user: dict = Depends(get_current_user)):
    try:
        result = await streak_system.get_history(current_user["id"], page, limit, timezone)
        return RitualHistoryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{ritual_id}", response_model=RitualUpdateResponse, status_code=status.HTTP_200_OK)
async def update_ritual(
    ritual_id: str,
    ritual_type: Optional[RitualType] = Form(None, description="The type of ritual completed"),
    text: Optional[str] = Form(None, description="Optional text submission for the ritual"),
    file: Optional[UploadFile] = File(None, description="Optional file upload for the ritual"),
    clear_file: bool = Form(False, description="Clear existing attached file"),
    timezone: str = Form("UTC", description="Client's timezone"),
    time: Optional[str] = Form(None, description="Time of completion in 12h format"),
    time_name: Optional[str] = Form(None, description="Time name"),
    current_user: dict = Depends(get_current_user)
):
    try:
        ritual_type_val = ritual_type.value if ritual_type else None
        result = await streak_system.update_ritual(
            user_id=current_user["id"],
            ritual_id=ritual_id,
            ritual_type=ritual_type_val,
            text=text,
            file=file,
            clear_file=clear_file,
            timezone=timezone,
            time=time,
            time_name=time_name
        )
        return RitualUpdateResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST if "format" in str(e) else status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.delete("/{ritual_id}", response_model=RitualDeleteResponse, status_code=status.HTTP_200_OK)
async def delete_ritual(
    ritual_id: str,
    timezone: str = Query("UTC", description="Client's timezone"),
    current_user: dict = Depends(get_current_user)
):
    try:
        result = await streak_system.delete_ritual(
            user_id=current_user["id"],
            ritual_id=ritual_id,
            timezone=timezone
        )
        return RitualDeleteResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST if "format" in str(e) else status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
