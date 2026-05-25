from pydantic import BaseModel, EmailStr
from typing import Optional


class UserRegister(BaseModel):
    email: str
    username: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    credits: int
    is_active: bool

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ScanHistoryItem(BaseModel):
    id: int
    category: str
    brands: str
    total_items: int
    opportunities_found: int
    avg_margin: float
    avg_profit: float
    created_at: str

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    total_scans: int
    total_opportunities: int
    avg_margin_all: float
    avg_profit_all: float
    top_categories: list[dict]
    scan_history: list[ScanHistoryItem]
