from pydantic import BaseModel, Field, AliasChoices, field_validator, model_validator
import re
import datetime
from typing import Optional, Dict, Any

class RelationshipCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Name")
    city_name: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("city_name", "City Name"),
        description="City Name"
    )
    relationship_start_date: str = Field(
        ...,
        validation_alias=AliasChoices(
            "relationship_start_date",
            "relationship start date",
            "relationship start date (mm.dd,yyyy)"
        ),
        description="Relationship start date (mm.dd,yyyy or mm.dd.yyyy)"
    )
    is_long_distance: bool = Field(
        ...,
        validation_alias=AliasChoices(
            "is_long_distance",
            "is logn distance relation",
            "is long distance relation"
        ),
        description="Is long distance relation [true/false]"
    )

    model_config = {
        "populate_by_name": True
    }

    @field_validator("relationship_start_date")
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        # Match exactly MM.DD.YYYY or MM.DD,YYYY
        if not re.match(r"^\d{2}[\.,]\d{2}[\.,]\d{4}$", v):
            raise ValueError("Relationship start date must be in mm.dd.yyyy or mm.dd,yyyy format")
        
        # Split by separator
        parts = re.split(r"[\.,]", v)
        month_str, day_str, year_str = parts[0], parts[1], parts[2]
        try:
            month = int(month_str)
            day = int(day_str)
            year = int(year_str)
        except ValueError:
            raise ValueError("Invalid digits in relationship start date")
        
        # Validate values
        if month < 1 or month > 12:
            raise ValueError("Month must be between 01 and 12")
        if day < 1 or day > 31:
            raise ValueError("Day must be between 01 and 31")
        if year < 1000 or year > 9999:
            raise ValueError("Year must be a 4-digit number")
        
        # Check if it's a valid calendar date
        try:
            datetime.date(year, month, day)
        except ValueError:
            raise ValueError("Invalid calendar date")
            
        return v

class PartnerInfo(BaseModel):
    user_id: str
    name: str
    city_name: str
    relationship_start_date: str
    is_long_distance: bool

class RelationshipResponseData(BaseModel):
    id: str = Field(..., validation_alias=AliasChoices("id", "_id"))
    name: str
    city_name: str
    relationship_start_date: str
    is_long_distance: bool
    secret_key: Optional[str] = None
    is_aligned: bool = False
    partner: Optional[PartnerInfo] = None

    model_config = {
        "populate_by_name": True
    }

    @model_validator(mode="after")
    def hide_secret_key_if_aligned(self) -> "RelationshipResponseData":
        if self.is_aligned or self.partner:
            self.secret_key = None
        return self

class RelationshipResponse(BaseModel):
    success: bool
    message: str
    data: RelationshipResponseData

class AlignRequest(BaseModel):
    secret_key: str = Field(
        ...,
        validation_alias=AliasChoices("secret_key", "partner_secret_key"),
        description="Secret key of the partner to connect with"
    )

class AlignResponse(BaseModel):
    success: bool
    message: str
    data: RelationshipResponseData
