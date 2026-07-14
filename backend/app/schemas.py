from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    conversation_id: Optional[str] = None
    user_id: str = "anonymous"
    channel: str = "api"
    use_dify: bool = False


class ChatResponse(BaseModel):
    conversation_id: str
    request_id: str
    answer: str
    route: str
    fallback: bool = False
    citations: list[str] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int


class TicketCreate(BaseModel):
    conversation_id: Optional[str] = None
    reason: str
    priority: Literal["low", "normal", "high"] = "normal"
    payload: dict[str, Any] = Field(default_factory=dict)


class TicketOut(BaseModel):
    id: int
    conversation_id: Optional[str]
    reason: str
    priority: str
    status: str
    created_at: datetime


class OrderLogistics(BaseModel):
    company: str
    tracking_no: str
    last_update: str
    detail: str


class OrderOut(BaseModel):
    order_id: str
    status: str
    status_code: str
    created_at: str
    product: str
    amount: float
    logistics: Optional[OrderLogistics] = None
    source: str = "mock-oms"


class TraceOut(BaseModel):
    id: int
    conversation_id: str
    request_id: str
    span: str
    status: str
    detail: dict[str, Any]
    latency_ms: Optional[int]
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    service: str
    public_base_url: str
    dify_configured: bool
