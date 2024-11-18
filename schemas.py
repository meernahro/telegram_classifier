from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class ChannelCreate(BaseModel):
    name: str


class ExchangeCreate(BaseModel):
    name: str


class TokenCreate(BaseModel):
    token: str
    exchange: str
    market: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TokenResponse(BaseModel):
    id: int
    token: str
    exchange: str
    market: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ChannelResponse(ChannelCreate):
    id: int

    class Config:
        from_attributes = True


class ExchangeResponse(ExchangeCreate):
    id: int

    class Config:
        from_attributes = True
