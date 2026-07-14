"""Resilient tool facade for Dify HTTP Request nodes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..config import Settings, get_settings
from ..services.http_tool import call_order_tool, degrade_message

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("/query_order")
async def query_order_tool(
    order_id: str = Query(..., min_length=6, max_length=32),
    force_fail: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
):
    """
    HTTP tool for Dify:
    - timeout + retry inside this facade
    - on failure returns degraded=true + handoff copy (never invent logistics)
    """
    result = await call_order_tool(
        order_id,
        settings,
        force_fail=force_fail,
        transport="direct",
    )
    if result.ok:
        return {
            "ok": True,
            "degraded": False,
            "attempts": result.attempts,
            "latency_ms": result.latency_ms,
            "data": result.data,
            "assistant_hint": (
                f"订单 {result.data.get('order_id')} 状态为 {result.data.get('status')}，"
                "请用自然语言向用户复述，勿编造未返回字段。"
            ),
        }

    return {
        "ok": False,
        "degraded": True,
        "fallback": "handoff",
        "attempts": result.attempts,
        "latency_ms": result.latency_ms,
        "error": result.error,
        "data": result.data,
        "assistant_hint": degrade_message(order_id, result.error or "unknown"),
    }
