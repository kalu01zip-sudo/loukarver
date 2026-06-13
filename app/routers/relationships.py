from fastapi import APIRouter, HTTPException, Depends, status
from app.schemas.relationships import RelationshipCreate, RelationshipResponse, AlignRequest, AlignResponse
from app.services.relationships import relationship_service
from app.routers.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

@router.post("/create", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_relationship(submission: RelationshipCreate, current_user: dict = Depends(get_current_user)):
    """
    Saves or updates the relationship profile details of the authenticated user.
    
    Accepts:
    - name: string
    - City Name (or city_name): string
    - relationship start date (or relationship_start_date) in format mm.dd,yyyy or mm.dd.yyyy
    - is logn distance relation (or is_long_distance) [true/false]
    """
    try:
        saved_data = await relationship_service.update_relationship_profile(current_user["id"], submission)
        return RelationshipResponse(
            success=True,
            message="Relationship details saved successfully!",
            data=saved_data
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred saving relationship data: {str(e)}"
        )

@router.post("/aligned", response_model=AlignResponse, status_code=status.HTTP_200_OK)
async def align_users(payload: AlignRequest, current_user: dict = Depends(get_current_user)):
    """
    Connects the authenticated user with another user using the partner's secret key.
    
    After connection:
    - Both users will have is_aligned set to true.
    - Each user will have the partner's information stored in their database record.
    """
    try:
        updated_user = await relationship_service.align_users(current_user["id"], payload.secret_key)
        return AlignResponse(
            success=True,
            message="Users successfully connected and aligned!",
            data=updated_user
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred connecting users: {str(e)}"
        )

@router.post("/break-alignment", response_model=AlignResponse, status_code=status.HTTP_200_OK)
async def break_alignment(current_user: dict = Depends(get_current_user)):
    """
    Breaks the connection between the authenticated user and their partner.
    """
    try:
        updated_user = await relationship_service.break_alignment(current_user["id"])
        return AlignResponse(
            success=True,
            message="Relationship alignment broken successfully.",
            data=updated_user
        )
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred breaking alignment: {str(e)}"
        )
