import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import Conversation, Message, TraceEvent, get_db
from ..schemas import TraceOut

router = APIRouter(prefix="/api/v1", tags=["observability"])


@router.get("/conversations/{conversation_id}/traces", response_model=list[TraceOut])
def list_traces(conversation_id: str, db: Session = Depends(get_db)):
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    rows = (
        db.query(TraceEvent)
        .filter(TraceEvent.conversation_id == conversation_id)
        .order_by(TraceEvent.id.asc())
        .all()
    )
    return [
        TraceOut(
            id=r.id,
            conversation_id=r.conversation_id,
            request_id=r.request_id,
            span=r.span,
            status=r.status,
            detail=json.loads(r.detail_json or "{}"),
            latency_ms=r.latency_ms,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.get("/conversations/{conversation_id}/messages")
def list_messages(conversation_id: str, db: Session = Depends(get_db)):
    if not db.get(Conversation, conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.asc())
        .all()
    )
    return [
        {
            "id": r.id,
            "role": r.role,
            "content": r.content,
            "meta": json.loads(r.meta_json or "{}"),
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


@router.get("/logs/recent")
def recent_logs(limit: int = 50, db: Session = Depends(get_db)):
    from ..db import RequestLog

    rows = db.query(RequestLog).order_by(RequestLog.id.desc()).limit(min(limit, 200)).all()
    return [
        {
            "id": r.id,
            "request_id": r.request_id,
            "method": r.method,
            "path": r.path,
            "status_code": r.status_code,
            "latency_ms": r.latency_ms,
            "client_ip": r.client_ip,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
