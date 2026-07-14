"""Mock OMS order catalog + intentional failure modes for tool-loop demos."""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import HTTPException

from ..schemas import OrderLogistics, OrderOut

ORDERS: dict[str, dict[str, Any]] = {
    "PP20260713001234": {
        "order_id": "PP20260713001234",
        "status": "已发货",
        "status_code": "shipped",
        "created_at": "2026-07-13 10:00:00",
        "product": "星眠 Pro 版 SS-200",
        "amount": 499.00,
        "logistics": {
            "company": "顺丰速运",
            "tracking_no": "SF1234567890",
            "last_update": "2026-07-13 18:00:00",
            "detail": "快件已到达【深圳转运中心】",
        },
    },
    "PP20260712005678": {
        "order_id": "PP20260712005678",
        "status": "待发货",
        "status_code": "pending_shipment",
        "created_at": "2026-07-12 15:30:00",
        "product": "星眠基础版 SS-100",
        "amount": 299.00,
        "logistics": None,
    },
    "PP20260711009999": {
        "order_id": "PP20260711009999",
        "status": "已完成",
        "status_code": "completed",
        "created_at": "2026-07-11 09:12:00",
        "product": "星眠 Max 版 SS-300",
        "amount": 699.00,
        "logistics": {
            "company": "中通快递",
            "tracking_no": "ZT9876543210",
            "last_update": "2026-07-12 11:20:00",
            "detail": "已签收，签收人：本人",
        },
    },
}


def to_order_out(raw: dict[str, Any]) -> OrderOut:
    logistics = raw.get("logistics")
    return OrderOut(
        order_id=raw["order_id"],
        status=raw["status"],
        status_code=raw["status_code"],
        created_at=raw["created_at"],
        product=raw["product"],
        amount=raw["amount"],
        logistics=OrderLogistics(**logistics) if logistics else None,
        source="mock-oms",
    )


async def get_order(
    order_id: str,
    *,
    force_fail: Optional[str] = None,
    delay_ms: int = 0,
) -> OrderOut:
    """Fetch mock order. Supports force_fail=timeout|500|503 for chaos tests."""
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)

    if force_fail == "timeout":
        await asyncio.sleep(30)
        raise HTTPException(status_code=504, detail="simulated timeout")
    if force_fail == "500":
        raise HTTPException(status_code=500, detail="simulated OMS internal error")
    if force_fail == "503":
        raise HTTPException(status_code=503, detail="simulated OMS unavailable")

    raw = ORDERS.get(order_id.strip().upper()) or ORDERS.get(order_id.strip())
    if not raw:
        # also try exact key
        raw = ORDERS.get(order_id)
    if not raw:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "order_not_found",
                "message": "未找到该订单号，请核对后重试或转人工",
                "order_id": order_id,
            },
        )
    return to_order_out(raw)
