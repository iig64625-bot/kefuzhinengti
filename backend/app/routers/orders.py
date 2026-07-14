from fastapi import APIRouter, Query

from ..schemas import OrderOut
from ..services.orders import ORDERS, get_order, to_order_out

router = APIRouter(prefix="/api/v1", tags=["orders"])


@router.get("/orders", response_model=list[OrderOut])
def list_orders():
    return [to_order_out(v) for v in ORDERS.values()]


@router.get("/orders/{order_id}", response_model=OrderOut)
async def read_order(
    order_id: str,
    force_fail: str | None = Query(
        default=None,
        description="Chaos: timeout | 500 | 503 — for retry/degrade demos",
    ),
    delay_ms: int = Query(default=0, ge=0, le=10000),
):
    return await get_order(order_id, force_fail=force_fail, delay_ms=delay_ms)
