from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import Conversation, Message, Ticket, get_db
from ..schemas import ChatRequest, ChatResponse, TicketCreate, TicketOut
from ..services.dify_client import chat_via_dify
from ..services.http_tool import call_order_tool, degrade_message
from ..services.rag_local import LocalKnowledgeIndex, route_and_answer
from ..services.tracing import add_trace

router = APIRouter(prefix="/api/v1", tags=["chat"])

_index: LocalKnowledgeIndex | None = None


def get_index(settings: Settings = Depends(get_settings)) -> LocalKnowledgeIndex:
    global _index
    if _index is None:
        _index = LocalKnowledgeIndex(settings.knowledge_dir)
    return _index


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    index: LocalKnowledgeIndex = Depends(get_index),
):
    t0 = time.perf_counter()
    request_id = uuid.uuid4().hex
    conversation_id = body.conversation_id or uuid.uuid4().hex

    conv = db.get(Conversation, conversation_id)
    if not conv:
        conv = Conversation(
            id=conversation_id,
            user_id=body.user_id,
            channel=body.channel,
        )
        db.add(conv)
        db.flush()

    db.add(
        Message(
            conversation_id=conversation_id,
            role="user",
            content=body.query,
            meta_json=json.dumps({"request_id": request_id}, ensure_ascii=False),
        )
    )
    add_trace(
        db,
        conversation_id=conversation_id,
        request_id=request_id,
        span="chat.request",
        detail={"query": body.query, "channel": body.channel},
    )

    tool_calls: list[dict] = []
    citations: list[str] = []
    fallback = False
    route = "unknown"
    answer = ""

    # Prefer Dify when explicitly requested and configured
    history_bits: list[str] = []
    prior = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id, Message.role == "user")
        .order_by(Message.id.desc())
        .limit(3)
        .all()
    )
    # exclude the message we just inserted (same content as body.query at end)
    for m in reversed(prior[1:] if prior and prior[0].content == body.query else prior):
        history_bits.append(m.content)
    retrieval_query = " ".join(history_bits + [body.query]) if history_bits else body.query

    if body.use_dify and settings.dify_api_key:
        try:
            t_dify = time.perf_counter()
            raw = await chat_via_dify(
                settings,
                query=body.query,
                user=body.user_id,
                conversation_id=None,
            )
            answer = raw.get("answer") or ""
            route = "dify"
            citations = ["dify"]
            add_trace(
                db,
                conversation_id=conversation_id,
                request_id=request_id,
                span="dify.chat",
                status="ok",
                detail={"conversation_id": raw.get("conversation_id")},
                latency_ms=int((time.perf_counter() - t_dify) * 1000),
            )
        except Exception as exc:  # noqa: BLE001
            add_trace(
                db,
                conversation_id=conversation_id,
                request_id=request_id,
                span="dify.chat",
                status="error",
                detail={"error": str(exc)},
            )
            fallback = True
            route = "dify_failed_fallback"
            answer = (
                "上游智能体暂时不可用，已降级到本地知识库。"
                "如需人工请拨打 400-888-3366。"
            )

    if not answer or route.endswith("fallback"):
        local = route_and_answer(retrieval_query if not answer else body.query, index)
        # keep user-facing query for order detection
        if "order_id" not in local:
            local2 = route_and_answer(body.query, index)
            if local2.get("order_id"):
                local = local2
            elif local.get("route") == "rag_local" and history_bits:
                # answered from context-enhanced retrieval
                pass
        if not answer:
            answer = local["answer"]
            route = local["route"]
            fallback = local["fallback"]
            citations = local.get("citations") or []
        elif route == "dify_failed_fallback":
            # merge: keep notice + local answer
            answer = answer + "\n\n" + local["answer"]
            citations = local.get("citations") or []
            fallback = fallback or local["fallback"]
            route = local["route"] + "+dify_degraded"

        add_trace(
            db,
            conversation_id=conversation_id,
            request_id=request_id,
            span="rag.retrieve_answer",
            status="fallback" if fallback else "ok",
            detail={"route": route, "citations": citations},
        )

        # Real HTTP tool loop when order_id detected
        order_id = local.get("order_id")
        if not order_id:
            m = re.search(r"(PP\d{14})", body.query, re.I)
            if m and any(k in body.query for k in ("订单", "物流", "查", "快递")):
                order_id = m.group(1).upper()

        if order_id:
            t_tool = time.perf_counter()
            # direct transport avoids same-process HTTP deadlock; Dify uses HTTP facade
            tool = await call_order_tool(order_id, settings, transport="direct")
            tool_calls.append(
                {
                    "tool": "query_order",
                    "order_id": order_id,
                    "ok": tool.ok,
                    "attempts": tool.attempts,
                    "error": tool.error,
                    "degraded": tool.degraded,
                    "latency_ms": tool.latency_ms,
                    "transport": tool.transport,
                }
            )
            add_trace(
                db,
                conversation_id=conversation_id,
                request_id=request_id,
                span="tool.query_order",
                status="ok" if tool.ok else "degraded",
                detail={
                    "order_id": order_id,
                    "attempts": tool.attempts,
                    "error": tool.error,
                    "data": tool.data,
                },
                latency_ms=int((time.perf_counter() - t_tool) * 1000),
            )
            if tool.ok and tool.data:
                data = tool.data
                logistics = data.get("logistics") or {}
                log_line = ""
                if logistics:
                    log_line = (
                        f"物流：{logistics.get('company')} {logistics.get('tracking_no')}，"
                        f"{logistics.get('detail')}（更新于 {logistics.get('last_update')}）"
                    )
                answer = (
                    f"已通过 HTTP 订单接口查询到订单 {data.get('order_id')}：\n"
                    f"- 状态：{data.get('status')}（{data.get('status_code')}）\n"
                    f"- 商品：{data.get('product')}，金额 ¥{data.get('amount')}\n"
                    f"- 下单时间：{data.get('created_at')}\n"
                    + (f"- {log_line}\n" if log_line else "- 暂无物流信息\n")
                )
                route = "tool_query_order"
                fallback = False
                citations = ["mock-oms-http"]
            else:
                answer = degrade_message(order_id, tool.error or "unknown")
                route = "tool_query_order_degraded"
                fallback = True
                # auto-create ticket on tool failure
                ticket = Ticket(
                    conversation_id=conversation_id,
                    reason="order_tool_failed",
                    priority="high",
                    payload_json=json.dumps(
                        {"order_id": order_id, "error": tool.error, "request_id": request_id},
                        ensure_ascii=False,
                    ),
                )
                db.add(ticket)
                add_trace(
                    db,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    span="ticket.created",
                    detail={"reason": "order_tool_failed"},
                )

    latency_ms = int((time.perf_counter() - t0) * 1000)
    db.add(
        Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            meta_json=json.dumps(
                {
                    "request_id": request_id,
                    "route": route,
                    "fallback": fallback,
                    "citations": citations,
                    "tool_calls": tool_calls,
                },
                ensure_ascii=False,
            ),
        )
    )
    conv.updated_at = datetime.utcnow()
    add_trace(
        db,
        conversation_id=conversation_id,
        request_id=request_id,
        span="chat.response",
        status="fallback" if fallback else "ok",
        detail={"route": route},
        latency_ms=latency_ms,
    )
    db.commit()

    return ChatResponse(
        conversation_id=conversation_id,
        request_id=request_id,
        answer=answer,
        route=route,
        fallback=fallback,
        citations=citations,
        tool_calls=tool_calls,
        latency_ms=latency_ms,
    )


@router.post("/tickets", response_model=TicketOut)
def create_ticket(body: TicketCreate, db: Session = Depends(get_db)):
    ticket = Ticket(
        conversation_id=body.conversation_id,
        reason=body.reason,
        priority=body.priority,
        payload_json=json.dumps(body.payload, ensure_ascii=False),
    )
    db.add(ticket)
    if body.conversation_id:
        add_trace(
            db,
            conversation_id=body.conversation_id,
            request_id=uuid.uuid4().hex,
            span="ticket.created",
            detail={"reason": body.reason, "priority": body.priority},
        )
    db.commit()
    db.refresh(ticket)
    return TicketOut(
        id=ticket.id,
        conversation_id=ticket.conversation_id,
        reason=ticket.reason,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at,
    )
