from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class EnergyLevel(str, Enum):
    DRAINED = "Drained"
    FLAT = "Flat"
    STEADY = "Steady"
    ON = "On"
    LIT = "Lit"

class SleepLevel(str, Enum):
    DEPLETED = "Depleted"
    UNDER_SLEPT = "Under-Slept"
    ADEQUATE = "Adequate"
    RESTED = "Rested"

class StressLevel(str, Enum):
    LIGHT = "Light"
    MODERATE = "Moderate"
    HEAVY = "Heavy"
    MAX = "Max"

class EnergyBase(BaseModel):
    energy_level: EnergyLevel
    sleep: SleepLevel
    stress: StressLevel
    notes: Optional[str] = None
    share_with_partner: bool = True

class EnergyCreate(EnergyBase):
    pass

class EnergyUpdate(BaseModel):
    energy_level: Optional[EnergyLevel] = None
    sleep: Optional[SleepLevel] = None
    stress: Optional[StressLevel] = None
    notes: Optional[str] = None
    share_with_partner: Optional[bool] = None

class EnergyPatchShare(BaseModel):
    share_with_partner: bool

class EnergyRead(EnergyBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

class EnergyResponse(BaseModel):
    success: bool
    data: EnergyRead

class EnergyListResponse(BaseModel):
    success: bool
    data: List[EnergyRead]

class GenericResponse(BaseModel):
    success: bool
    message: str
