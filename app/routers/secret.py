from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Form, Query
from fastapi.responses import FileResponse
from typing import List

from app.routers.auth import get_current_user
from app.schemas.secret import (
    SecretRead, SecretPaginatedResponse, GenericResponse,
    SecretPatchScreenshot
)
from app.services.secret import secret_service

router = APIRouter(prefix="/secret", tags=["Secret"])

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

@router.post("/upload", response_model=GenericResponse, status_code=status.HTTP_201_CREATED)
async def upload_secret(
    file: UploadFile = File(...),
    prevent_screenshot: bool = Form(True),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a secret file for your partner. Max size: 100MB.
    `prevent_screenshot`: If true, hints the client to block screenshots/recording.
    """
    try:
        await secret_service.save_secret(current_user["id"], file, prevent_screenshot)
        return GenericResponse(success=True, message="Secret sent to partner!")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/received", response_model=SecretPaginatedResponse)
async def list_received_secrets(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List unviewed secrets received from your partner (Paginated)."""
    try:
        data, total = await secret_service.get_secrets_for_me(current_user["id"], page, size)
        return SecretPaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sent", response_model=SecretPaginatedResponse)
async def list_sent_secrets(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List unviewed secrets you sent to your partner (Paginated)."""
    try:
        data, total = await secret_service.get_sent_secrets(current_user["id"], page, size)
        return SecretPaginatedResponse(success=True, data=data, total=total, page=page, size=size)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/{secret_id}/screenshot", response_model=GenericResponse)
async def patch_screenshot_protection(
    secret_id: str,
    payload: SecretPatchScreenshot,
    current_user: dict = Depends(get_current_user)
):
    """Update the screenshot protection state for a secret you sent."""
    try:
        success = await secret_service.patch_screenshot_protection(
            secret_id, current_user["id"], payload.prevent_screenshot
        )
        if not success:
            raise HTTPException(status_code=404, detail="Secret not found or not owned by you.")
        return GenericResponse(success=True, message="Screenshot protection updated.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/view/{secret_id}")
async def view_secret(
    secret_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Open and view a secret file. 
    - If you are the RECIPIENT: The file is deleted from the server immediately after viewing.
    - If you are the SENDER: You can view it without triggering deletion.
    """
    try:
        doc = await secret_service.get_secret_metadata(secret_id, current_user["id"])
        file_path = secret_service.get_full_path(doc["stored_filename"])
        
        # If recipient is viewing, trigger one-time-view logic
        if doc["recipient_id"] == current_user["id"]:
            await secret_service.mark_secret_viewed(secret_id)
            background_tasks.add_task(secret_service.delete_file, file_path)
        
        return FileResponse(
            path=file_path,
            filename=doc["filename"],
            media_type=doc["file_type"]
        )
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
