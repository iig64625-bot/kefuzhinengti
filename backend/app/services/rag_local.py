"""Local keyword RAG used when Dify is not configured — keeps demo self-contained."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    doc_id: str
    title: str
    text: str


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    cleaned = re.sub(r"\s+", "", text.lower())
    grams: set[str] = set()
    # CJK bigrams
    cjk = re.findall(r"[\u4e00-\u9fff]+", cleaned)
    for run in cjk:
        if len(run) < n:
            if run:
                grams.add(run)
            continue
        for i in range(len(run) - n + 1):
            grams.add(run[i : i + n])
    # alnum tokens
    for tok in re.findall(r"[a-z0-9\-]{2,}", cleaned):
        grams.add(tok)
    return grams


class LocalKnowledgeIndex:
    def __init__(self, knowledge_dir: str | Path) -> None:
        self.chunks: list[Chunk] = []
        self.faq_pairs: list[tuple[str, str, str]] = []  # (q, a, doc_id)
        root = Path(knowledge_dir)
        if not root.exists():
            alt = root.parent.parent / "knowledge-base"
            root = alt if alt.exists() else root
        for path in sorted(root.glob("0*.md")):
            text = path.read_text(encoding="utf-8")
            # FAQ blocks: **Q：...** / A：...
            for m in re.finditer(
                r"\*\*Q[:：]\s*(.*?)\*\*\s*\n+(?:A[:：]\s*)?(.*?)(?=\n\*\*Q[:：]|\n## |\Z)",
                text,
                flags=re.S,
            ):
                q = re.sub(r"\s+", "", m.group(1))
                a = m.group(2).strip()
                if q and a:
                    self.faq_pairs.append((q, a, path.stem))
            # Also **Q：...** with bullet answers under (no A:)
            for m in re.finditer(
                r"\*\*Q[:：]\s*(.*?)\*\*\s*\n((?:[-*].*\n?)+)",
                text,
            ):
                q = re.sub(r"\s+", "", m.group(1))
                a = m.group(2).strip()
                if q and a and not any(q == existing for existing, _, _ in self.faq_pairs):
                    self.faq_pairs.append((q, a, path.stem))

            sections = re.split(r"\n(?=## )", text)
            for sec in sections:
                sec = sec.strip()
                if len(sec) < 40:
                    continue
                title = sec.splitlines()[0].lstrip("# ").strip()
                self.chunks.append(Chunk(doc_id=path.stem, title=title, text=sec))

    def retrieve(self, query: str, top_k: int = 4) -> list[Chunk]:
        q = _char_ngrams(query)
        if not q:
            return []
        scored: list[tuple[float, Chunk]] = []
        for chunk in self.chunks:
            tokens = _char_ngrams(chunk.text)
            if not tokens:
                continue
            overlap = len(q & tokens)
            if overlap == 0:
                continue
            score = overlap / (len(q) ** 0.5 + 1e-6)
            # title / exact FAQ boost
            if any(g in chunk.title for g in list(q)[:8]):
                score += 1.5
            scored.append((score, chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_k]]

    def match_faq(self, query: str) -> tuple[str, str, str] | None:
        q_norm = re.sub(r"\s+", "", query)
        q_grams = _char_ngrams(query)
        best = None
        best_score = 0.0
        for faq_q, faq_a, doc_id in self.faq_pairs:
            grams = _char_ngrams(faq_q)
            if not grams:
                continue
            inter = len(q_grams & grams)
            score = inter / (len(q_grams) ** 0.5 + 1e-6)
            # strong exact / containment
            if faq_q in q_norm or q_norm in faq_q:
                score += 8
            # specific cue pairs (avoid vague 「退款」alone)
            cues = [
                ("包邮", "包邮"),
                ("孕妇", "孕妇"),
                ("保修", "保修"),
                ("蓝牙", "蓝牙"),
                ("搜不到", "搜不到"),
                ("热敷不热", "热敷不热"),
                ("热敷", "热敷"),
                ("几档", "热敷"),
                ("枕套", "机洗"),
                ("机洗", "机洗"),
                ("多久到账", "多久到账"),
                ("多久到账", "到账"),
                ("到账", "多久到账"),
                ("被拒绝", "被拒绝"),
                ("拒绝了", "被拒绝"),
                ("签收但", "签收但"),
                ("不更新", "不更新"),
                ("改收货", "改收货"),
                ("改地址", "改收货"),
            ]
            for q_cue, f_cue in cues:
                if q_cue in q_norm and f_cue in faq_q:
                    score += 5
            # hard negatives: "到哪里" ≠ "多久到账", "热敷不热" ≠ "有热敷吗"
            if "多久到账" in q_norm and "退到哪里" in faq_q:
                continue
            if ("被拒绝" in q_norm or "拒绝了" in q_norm) and "退到哪里" in faq_q:
                continue
            if "热敷" in q_norm and "几档" in q_norm and "不热" in faq_q:
                continue
            # penalize weak generic-only overlap
            if inter <= 2 and score < 6:
                continue
            if score > best_score:
                best_score = score
                best = (faq_q, faq_a, doc_id)
        if best and best_score >= 4.5:
            return best
        return None


HANDFF_KEYWORDS = ("投诉", "维权", "律师", "报警", "转人工", "人工客服", "辱骂")
SAFETY_OVERHEAT = ("过热", "冒烟", "异味", "烫伤", "着火")


def route_and_answer(query: str, index: LocalKnowledgeIndex) -> dict:
    q = query.strip()

    if any(k in q for k in SAFETY_OVERHEAT):
        return {
            "answer": (
                "请立即停止使用该产品并断电/停止热敷。"
                "请拨打客服热线 400-888-3366 报修与安全指导，不要继续使用。"
            ),
            "route": "safety",
            "fallback": False,
            "citations": ["safety-policy"],
        }

    if re.search(r"1[3-9]\d{9}", q) and ("订单" in q or "物流" in q):
        return {
            "answer": (
                "抱歉，我无法根据手机号代查他人订单。"
                "请使用下单账号登录 App「我的 → 我的订单」查询，"
                "或提供本人订单号；需要协助可转人工（400-888-3366）。"
            ),
            "route": "privacy",
            "fallback": False,
            "citations": ["safety-policy"],
        }

    if any(k in q for k in HANDFF_KEYWORDS):
        return {
            "answer": (
                "已为您标记转人工。请稍候，或直接拨打 400-888-3366 / "
                "发送邮件至 service@starsleep.cn，并说明会话与订单号。"
            ),
            "route": "handoff",
            "fallback": True,
            "citations": [],
        }

    m = re.search(r"(PP\d{14})", q, re.I)
    if m and ("订单" in q or "物流" in q or "查" in q or "快递" in q):
        return {
            "answer": (
                f"检测到订单号 {m.group(1).upper()}。"
                "正在调用订单查询接口获取实时状态。"
            ),
            "route": "order_tool",
            "fallback": False,
            "citations": ["mock-oms"],
            "order_id": m.group(1).upper(),
        }

    faq = index.match_faq(q)
    if faq:
        faq_q, faq_a, doc_id = faq
        return {
            "answer": f"根据知识库（对应问题：{faq_q}）：\n\n{faq_a}",
            "route": "faq_match",
            "fallback": False,
            "citations": [f"{doc_id}::FAQ"],
        }

    hits = index.retrieve(q, top_k=4)
    if not hits:
        return {
            "answer": (
                "抱歉，当前知识库未检索到足够依据，我不想猜测。"
                "您可以换个问法，或拨打人工客服 400-888-3366。"
            ),
            "route": "fallback_empty_retrieval",
            "fallback": True,
            "citations": [],
        }

    parts = []
    citations = []
    for h in hits[:3]:
        citations.append(f"{h.doc_id}::{h.title}")
        snippet = re.sub(r"\n{2,}", "\n", h.text)[:520]
        parts.append(snippet)

    body = "\n\n".join(parts)
    answer = (
        "根据知识库，为您整理如下要点：\n\n"
        f"{body}\n\n"
        "如需核对订单实时状态，请提供订单号（格式 PP+日期+数字）。"
        "涉及质量安全请立即停用并联系 400-888-3366。"
    )
    return {
        "answer": answer,
        "route": "rag_local",
        "fallback": False,
        "citations": citations,
    }
