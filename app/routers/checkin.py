from fastapi import APIRouter, HTTPException, Depends, status, Query
from app.schemas.checkin import CheckInCreate, CheckInUpdate, CheckInResponse, CheckInResponseData, CheckInQuestionsResponse, CheckInQuestionsResponseData
from app.services.checkin import checkin_service
from app.routers.auth import get_current_user

router = APIRouter(prefix="/check-in", tags=["Check-In"])

@router.get("/questions", response_model=CheckInQuestionsResponse, status_code=status.HTTP_200_OK)
async def get_questions_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Retrieves the three check-in questions.
    """
    try:
        questions = await checkin_service.get_questions()
        return CheckInQuestionsResponse(
            success=True,
            message="Questions retrieved successfully.",
            data=CheckInQuestionsResponseData(**questions)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred fetching questions: {str(e)}"
        )

@router.get("", response_model=CheckInResponse, status_code=status.HTTP_200_OK)
async def get_checkin(date: str = Query(..., description="Date to fetch the check-in for, e.g. mm.dd.yyyy"), current_user: dict = Depends(get_current_user)):
    """
    Retrieves the check-in for the specified date.
    Returns whether the partner has submitted, and includes the user's answers.
    Also includes partner's answers if they have submitted.
    """
    try:
        data = await checkin_service.get_checkin(current_user["id"], date)
        return CheckInResponse(
            success=True,
            message="Check-in data retrieved successfully.",
            data=CheckInResponseData(**data)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred fetching check-in: {str(e)}"
        )

@router.post("", response_model=CheckInResponse, status_code=status.HTTP_201_CREATED)
async def create_checkin(payload: CheckInCreate, current_user: dict = Depends(get_current_user)):
    """
    Saves a new check-in for the user.
    """
    try:
        inserted = await checkin_service.create_checkin(current_user["id"], payload)
        # Fetch updated data to include partner status
        data = await checkin_service.get_checkin(current_user["id"], payload.date)
        return CheckInResponse(
            success=True,
            message="Check-in saved successfully.",
            data=CheckInResponseData(**data)
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred saving check-in: {str(e)}"
        )

@router.patch("", response_model=CheckInResponse, status_code=status.HTTP_200_OK)
async def update_checkin(payload: CheckInUpdate, current_user: dict = Depends(get_current_user)):
    """
    Updates an existing check-in for the user.
    """
    try:
        updated = await checkin_service.update_checkin(current_user["id"], payload)
        # Fetch updated data to include partner status
        data = await checkin_service.get_checkin(current_user["id"], payload.date)
        return CheckInResponse(
            success=True,
            message="Check-in updated successfully.",
            data=CheckInResponseData(**data)
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred updating check-in: {str(e)}"
        )
