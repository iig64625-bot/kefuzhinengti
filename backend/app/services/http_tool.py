"""Order tool with timeout/retry/degrade — direct or HTTP transport."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import HTTPException

from ..config import Settings
from .orders import get_order


@dataclass
class ToolResult:
    ok: bool
    data: Optional[dict[str, Any]]
    error: Optional[str]
    attempts: int
    degraded: bool
    latency_ms: int
    transport: str = "direct"


def degrade_message(order_id: str, error: str) -> str:
    return (
        f"订单号 {order_id} 实时查询暂时失败（原因：{error}）。"
        "我不会编造物流信息。已为您准备转人工："
        "请拨打 400-888-3366，或回复「转人工」留下订单号与手机号后四位。"
    )


async def _attempt_direct(order_id: str, force_fail: Optional[str]) -> dict[str, Any]:
    order = await get_order(order_id, force_fail=force_fail)
    return order.model_dump()


async def call_order_tool(
    order_id: str,
    settings: Settings,
    *,
    force_fail: Optional[str] = None,
    transport: str = "direct",
    base_url: Optional[str] = None,
) -> ToolResult:
    """
    transport=direct: in-process (avoids self-HTTP deadlock under single worker)
    transport=http: real HTTP GET — for Dify / external clients / e2e tests
    """
    attempts = 0
    last_err: Optional[str] = None
    start = asyncio.get_event_loop().time()
    max_retries = settings.order_http_max_retries
    timeout = settings.order_http_timeout_sec
    backoff = settings.order_http_retry_backoff_sec
    url_base = (base_url or settings.public_base_url).rstrip("/")

    while attempts <= max_retries:
        attempts += 1
        try:
            if transport == "http":
                url = f"{url_base}/api/v1/orders/{order_id}"
                params = {"force_fail": force_fail} if force_fail else None
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(url, params=params)
                    if resp.status_code == 404:
                        elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
                        return ToolResult(
                            ok=False,
                            data=resp.json() if resp.content else None,
                            error="order_not_found",
                            attempts=attempts,
                            degraded=True,
                            latency_ms=elapsed,
                            transport="http",
                        )
                    if resp.status_code >= 500:
                        last_err = f"http_{resp.status_code}"
                        if attempts <= max_retries:
                            await asyncio.sleep(backoff * attempts)
                            continue
                        break
                    resp.raise_for_status()
                    elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
                    return ToolResult(
                        ok=True,
                        data=resp.json(),
                        error=None,
                        attempts=attempts,
                        degraded=False,
                        latency_ms=elapsed,
                        transport="http",
                    )
            else:
                data = await _attempt_direct(order_id, force_fail)
                elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
                return ToolResult(
                    ok=True,
                    data=data,
                    error=None,
                    attempts=attempts,
                    degraded=False,
                    latency_ms=elapsed,
                    transport="direct",
                )
        except HTTPException as exc:
            if exc.status_code == 404:
                elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
                return ToolResult(
                    ok=False,
                    data=exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail},
                    error="order_not_found",
                    attempts=attempts,
                    degraded=True,
                    latency_ms=elapsed,
                    transport=transport,
                )
            if exc.status_code >= 500:
                last_err = f"http_{exc.status_code}"
                if attempts <= max_retries:
                    await asyncio.sleep(backoff * attempts)
                    continue
                break
            last_err = str(exc.detail)
            break
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_err = type(exc).__name__
            if attempts <= max_retries:
                await asyncio.sleep(backoff * attempts)
                continue
            break
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
            break

    elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
    return ToolResult(
        ok=False,
        data=None,
        error=last_err or "unknown_error",
        attempts=attempts,
        degraded=True,
        latency_ms=elapsed,
        transport=transport,
    )


# Back-compat alias
async def call_order_api(
    base_url: str,
    order_id: str,
    settings: Settings,
    *,
    force_fail: Optional[str] = None,
) -> ToolResult:
    return await call_order_tool(
        order_id,
        settings,
        force_fail=force_fail,
        transport="http",
        base_url=base_url,
    )
