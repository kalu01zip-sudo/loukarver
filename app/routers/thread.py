from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from typing import List, Optional

from app.routers.auth import get_current_user
from app.schemas.thread import (
    ThreadCategoryResponse, LetterCreate, PhotoCreate, PromptAskCreate, PromptReplyUpdate,
    AppreciationCreate, CheckInThreadCreate, ThreadMessageResponse,
    PromptType, PromptQuestion, PromptQuestionCreate, GenericResponse,
    LetterUpdate, PhotoUpdate, VoiceUpdate, PromptAskUpdate, AppreciationUpdate, CheckInThreadUpdate
)
from app.services.thread import thread_service

router = APIRouter(prefix="/thread", tags=["Thread"])

@router.get("/categories", response_model=ThreadCategoryResponse)
async def get_categories(current_user: dict = Depends(get_current_user)):
    """Get all available message categories for the thread."""
    return ThreadCategoryResponse(success=True, data=await thread_service.get_categories(current_user["id"]))

@router.get("/messages", response_model=List[ThreadMessageResponse])
async def get_messages(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    timezone: str = Query("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Get all shared messages in the thread (Paginated)."""
    messages, _ = await thread_service.get_messages(current_user["id"], page, size, timezone)
    return messages

@router.delete("/{message_id}", response_model=GenericResponse)
async def delete_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a message you sent to the thread."""
    try:
        success = await thread_service.delete_message(current_user["id"], message_id)
        if not success:
            raise HTTPException(status_code=404, detail="Message not found or permission denied.")
        return GenericResponse(success=True, message="Message deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Category Specific POST & PATCH Endpoints ---

@router.post("/letter", response_model=ThreadMessageResponse)
async def post_letter(payload: LetterCreate, current_user: dict = Depends(get_current_user)):
    """Post a letter to the thread."""
    try:
        return await thread_service.post_letter(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/letter/{message_id}", response_model=ThreadMessageResponse)
async def patch_letter(message_id: str, payload: LetterUpdate, current_user: dict = Depends(get_current_user)):
    """Update a letter you sent."""
    try:
        return await thread_service.update_message(current_user["id"], message_id, payload.model_dump(exclude_unset=True), timezone_str=payload.timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/voice", response_model=ThreadMessageResponse)
async def post_voice(
    file: UploadFile = File(...),
    timezone: str = Form("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Post a voice message to the thread."""
    try:
        return await thread_service.post_voice(current_user["id"], file, timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/voice/{message_id}", response_model=ThreadMessageResponse)
async def patch_voice(
    message_id: str,
    file: Optional[UploadFile] = File(None),
    timezone: str = Form("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Update (replace) a voice message you sent."""
    try:
        return await thread_service.update_message(current_user["id"], message_id, {}, file=file, timezone_str=timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/photo", response_model=ThreadMessageResponse)
async def post_photo(
    file: UploadFile = File(...),
    caption: str = Form(...),
    timezone: str = Form("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Post a photo message to the thread."""
    try:
        return await thread_service.post_photo(current_user["id"], file, caption, timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/photo/{message_id}", response_model=ThreadMessageResponse)
async def patch_photo(
    message_id: str,
    file: Optional[UploadFile] = File(None),
    caption: Optional[str] = Form(None),
    timezone: str = Form("UTC"),
    current_user: dict = Depends(get_current_user)
):
    """Update a photo message (file and/or caption)."""
    try:
        updates = {}
        if caption is not None: updates["caption"] = caption
        return await thread_service.update_message(current_user["id"], message_id, updates, file=file, timezone_str=timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/prompt/ask", response_model=ThreadMessageResponse)
async def ask_prompt(payload: PromptAskCreate, current_user: dict = Depends(get_current_user)):
    """User asks a prompt question to their partner."""
    try:
        return await thread_service.ask_prompt(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/prompt/ask/{message_id}", response_model=ThreadMessageResponse)
async def patch_prompt_ask(message_id: str, payload: PromptAskUpdate, current_user: dict = Depends(get_current_user)):
    """Update an asked prompt question."""
    try:
        updates = payload.model_dump(exclude_unset=True)
        if "question_text" in updates: updates["question"] = updates.pop("question_text")
        return await thread_service.update_message(current_user["id"], message_id, updates, timezone_str=payload.timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/prompt/{message_id}/reply", response_model=ThreadMessageResponse)
async def reply_to_prompt(
    message_id: str, 
    payload: PromptReplyUpdate, 
    current_user: dict = Depends(get_current_user)
):
    """Partner replies to the asked prompt question."""
    try:
        return await thread_service.reply_to_prompt(
            current_user["id"], 
            message_id, 
            payload.answer, 
            payload.timezone
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/appreciation", response_model=ThreadMessageResponse)
async def post_appreciation(payload: AppreciationCreate, current_user: dict = Depends(get_current_user)):
    """Post an appreciation message."""
    try:
        return await thread_service.post_appreciation(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/appreciation/{message_id}", response_model=ThreadMessageResponse)
async def patch_appreciation(message_id: str, payload: AppreciationUpdate, current_user: dict = Depends(get_current_user)):
    """Update an appreciation message."""
    try:
        return await thread_service.update_message(current_user["id"], message_id, payload.model_dump(exclude_unset=True), timezone_str=payload.timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.post("/checkin", response_model=ThreadMessageResponse)
async def post_checkin(payload: CheckInThreadCreate, current_user: dict = Depends(get_current_user)):
    """Post a check-in reply."""
    try:
        return await thread_service.post_checkin(current_user["id"], payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.patch("/checkin/{message_id}", response_model=ThreadMessageResponse)
async def patch_checkin(message_id: str, payload: CheckInThreadUpdate, current_user: dict = Depends(get_current_user)):
    """Update a check-in reply."""
    try:
        return await thread_service.update_message(current_user["id"], message_id, payload.model_dump(exclude_unset=True), timezone_str=payload.timezone)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

# --- Prompt Question CRUD ---

@router.get("/prompt/questions", response_model=List[PromptQuestion])
async def get_prompt_questions(
    type: PromptType = Query(...),
    current_user: dict = Depends(get_current_user)
):
    """Get available prompt questions (Defaults + Custom)."""
    return await thread_service.get_prompt_questions(current_user["id"], type)

@router.post("/prompt/questions", response_model=PromptQuestion)
async def create_prompt_question(payload: PromptQuestionCreate, current_user: dict = Depends(get_current_user)):
    """Create a new custom prompt question for the couple."""
    return await thread_service.create_prompt_question(current_user["id"], payload)

@router.patch("/prompt/questions/{question_id}", response_model=PromptQuestion)
async def update_prompt_question(question_id: str, payload: PromptQuestionCreate, current_user: dict = Depends(get_current_user)):
    """Update a custom prompt question."""
    try:
        return await thread_service.update_prompt_question(current_user["id"], question_id, payload)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

@router.delete("/prompt/questions/{question_id}", response_model=GenericResponse)
async def delete_prompt_question(question_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a custom prompt question."""
    try:
        success = await thread_service.delete_prompt_question(current_user["id"], question_id)
        if not success:
            raise HTTPException(status_code=404, detail="Question not found or permission denied.")
        return GenericResponse(success=True, message="Question deleted.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
