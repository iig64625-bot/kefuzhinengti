from __future__ import annotations

from typing import Any, Optional

import httpx

from ..config import Settings


async def chat_via_dify(
    settings: Settings,
    *,
    query: str,
    user: str,
    conversation_id: Optional[str] = None,
) -> dict[str, Any]:
    if not settings.dify_api_key:
        raise RuntimeError("DIFY_API_KEY not configured")

    url = f"{settings.dify_api_base.rstrip('/')}/chat-messages"
    headers = {
        "Authorization": f"Bearer {settings.dify_api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "inputs": {},
        "query": query,
        "response_mode": "blocking",
        "user": user,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        return resp.json()
