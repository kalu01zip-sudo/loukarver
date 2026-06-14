from pydantic import BaseModel, Field
from typing import List, Optional

class SearchResultItem(BaseModel):
    id: str = Field(..., description="The track ID (e.g., YouTube Video ID)")
    title: str
    artist: str
    cover_url: Optional[str]
    provider: str = "youtube"

class SearchResponse(BaseModel):
    success: bool
    data: List[SearchResultItem]

class AddTrackRequest(BaseModel):
    id: str = Field(..., description="The track ID (e.g., YouTube Video ID)")
    title: str
    artist: str
    cover_url: Optional[str]
    provider: str = "youtube"

class AddTrackResponse(BaseModel):
    success: bool
    message: str

class SharedTrackItem(BaseModel):
    id: str
    title: str
    artist: str
    cover_url: Optional[str]
    added_by: str
    added_by_name: str
    is_partner: bool
    provider: str

class PlaylistResponse(BaseModel):
    success: bool
    data: List[SharedTrackItem]
