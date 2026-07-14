from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..db import TraceEvent


def add_trace(
    db: Session,
    *,
    conversation_id: str,
    request_id: str,
    span: str,
    status: str = "ok",
    detail: Optional[dict[str, Any]] = None,
    latency_ms: Optional[int] = None,
) -> TraceEvent:
    event = TraceEvent(
        conversation_id=conversation_id,
        request_id=request_id,
        span=span,
        status=status,
        detail_json=json.dumps(detail or {}, ensure_ascii=False),
        latency_ms=latency_ms,
    )
    db.add(event)
    return event
