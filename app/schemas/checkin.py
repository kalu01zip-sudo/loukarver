from pydantic import BaseModel, Field
from typing import Optional

class CheckInCreate(BaseModel):
    date: str = Field(..., description="Date of the check-in, e.g. mm.dd.yyyy or mmddyyyy")
    answer_1: str = Field(..., description="Answer to question 1: How are you feeling?")
    answer_2: str = Field(..., description="Answer to question 2: What do you need most?")
    answer_3: str = Field(..., description="Answer to question 3: One thing on your mind...")

class CheckInUpdate(BaseModel):
    date: str = Field(..., description="Date of the check-in to update")
    answer_1: Optional[str] = Field(None, description="Updated answer to question 1: How are you feeling?")
    answer_2: Optional[str] = Field(None, description="Updated answer to question 2: What do you need most?")
    answer_3: Optional[str] = Field(None, description="Updated answer to question 3: One thing on your mind...")

class CheckInData(BaseModel):
    id: str = Field(alias="_id")
    user_id: str
    date: str
    answer_1: str
    answer_2: str
    answer_3: str

    model_config = {
        "populate_by_name": True
    }

class CheckInResponseData(BaseModel):
    is_partner_submit: bool
    my_check_in: Optional[CheckInData] = None
    partner_check_in: Optional[CheckInData] = None

class CheckInResponse(BaseModel):
    success: bool
    message: str
    data: CheckInResponseData

class CheckInQuestionsResponseData(BaseModel):
    question_1: str
    question_2: str
    question_3: str

class CheckInQuestionsResponse(BaseModel):
    success: bool
    message: str
    data: CheckInQuestionsResponseData
