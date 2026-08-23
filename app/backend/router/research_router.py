import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.database import db
from backend.schemas import ConversationMessageResponse, ConversationResponse, ResearchRequest, ResearchResponse
from backend.service import WorkflowService, get_workflow_service
from backend.service.attachment_service import build_attachment_context, delete_attachments
from backend.deps import active_provider_for, current_user


router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _load_history_context(user_id: int, thread_id: str, limit: int = 12) -> str:
    """Load only this user's recent turns for the next agent request."""
    with db() as conn:
        rows = conn.execute(
            """SELECT role, content FROM conversation_messages
               WHERE user_id = ? AND thread_id = ?
               ORDER BY id DESC LIMIT ?""",
            (user_id, thread_id, limit),
        ).fetchall()
    if not rows:
        return ""
    lines = []
    for row in reversed(rows):
        content = str(row["content"])
        if len(content) > 6000:
            content = content[:6000] + "..."
        speaker = "用户" if row["role"] == "user" else "助手"
        lines.append(f"{speaker}：{content}")
    return "\n".join(lines)


def _conversation_title(query: str) -> str:
    title = " ".join(query.split()) or "新对话"
    return title[:60]


def _seed_legacy_conversations(user_id: int) -> None:
    """Expose conversations saved before the conversation index was introduced."""
    with db() as conn:
        thread_rows = conn.execute(
            """SELECT DISTINCT messages.thread_id FROM conversation_messages AS messages
               LEFT JOIN conversations ON conversations.user_id = messages.user_id
                   AND conversations.thread_id = messages.thread_id
               WHERE messages.user_id = ? AND conversations.id IS NULL""",
            (user_id,),
        ).fetchall()
        for thread_row in thread_rows:
            thread_id = thread_row["thread_id"]
            first_message = conn.execute(
                """SELECT content FROM conversation_messages
                   WHERE user_id = ? AND thread_id = ? AND role = 'user'
                   ORDER BY id ASC LIMIT 1""",
                (user_id, thread_id),
            ).fetchone()
            bounds = conn.execute(
                """SELECT MIN(created_at) AS created_at, MAX(created_at) AS updated_at
                   FROM conversation_messages WHERE user_id = ? AND thread_id = ?""",
                (user_id, thread_id),
            ).fetchone()
            conn.execute(
                """INSERT OR IGNORE INTO conversations(user_id, thread_id, title, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    user_id,
                    thread_id,
                    _conversation_title(first_message["content"] if first_message else ""),
                    bounds["created_at"],
                    bounds["updated_at"],
                ),
            )


def _save_turn(user_id: int, thread_id: str, query: str, answer: str) -> None:
    visible_query = query.strip() or "请分析我上传的资料，并提炼关键结论。"
    if not answer.strip():
        return
    with db() as conn:
        conn.execute(
            """INSERT INTO conversations(user_id, thread_id, title)
               VALUES (?, ?, ?)
               ON CONFLICT(user_id, thread_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP""",
            (user_id, thread_id, _conversation_title(visible_query)),
        )
        conn.executemany(
            "INSERT INTO conversation_messages(user_id, thread_id, role, content) VALUES (?, ?, ?, ?)",
            [(user_id, thread_id, "user", visible_query), (user_id, thread_id, "assistant", answer)],
        )


def _query_with_history(query: str, history: str) -> str:
    if not history:
        return query
    return (
        f"{query}\n\n"
        "以下是当前会话中较早的对话。请将其作为上下文，理解用户的省略、追问和指代；"
        "如果当前问题与历史无关，以当前问题为准。\n\n"
        f"[历史对话]\n{history}"
    )


@router.get("/conversations", response_model=list[ConversationResponse])
def conversations(user: dict = Depends(current_user)) -> list[ConversationResponse]:
    _seed_legacy_conversations(user["id"])
    with db() as conn:
        rows = conn.execute(
            """SELECT thread_id, title, updated_at FROM conversations
               WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 50""",
            (user["id"],),
        ).fetchall()
    return [ConversationResponse(**dict(row)) for row in rows]


@router.delete("/conversations/{thread_id}", status_code=204)
def delete_conversation(thread_id: str, user: dict = Depends(current_user)) -> None:
    with db() as conn:
        exists = conn.execute(
            """SELECT 1 FROM conversations WHERE user_id = ? AND thread_id = ?
               UNION SELECT 1 FROM conversation_messages WHERE user_id = ? AND thread_id = ?
               LIMIT 1""",
            (user["id"], thread_id, user["id"], thread_id),
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="对话不存在")
        conn.execute(
            "DELETE FROM conversation_messages WHERE user_id = ? AND thread_id = ?",
            (user["id"], thread_id),
        )
        conn.execute(
            "DELETE FROM conversations WHERE user_id = ? AND thread_id = ?",
            (user["id"], thread_id),
        )


@router.get("/history", response_model=list[ConversationMessageResponse])
def conversation_history(
    thread_id: str = Query(..., min_length=1, max_length=120),
    user: dict = Depends(current_user),
) -> list[ConversationMessageResponse]:
    with db() as conn:
        rows = conn.execute(
            """SELECT id, role, content, created_at FROM conversation_messages
               WHERE user_id = ? AND thread_id = ?
               ORDER BY id ASC LIMIT 200""",
            (user["id"], thread_id),
        ).fetchall()
    return [ConversationMessageResponse(**dict(row)) for row in rows]


@router.post("/run", response_model=ResearchResponse)
async def run_research(
    payload: ResearchRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    user: dict = Depends(current_user),
) -> ResearchResponse:
    provider = active_provider_for(user["id"])
    provider = _request_provider(provider, payload)
    attachment_ids = list(payload.attachment_ids or [])
    try:
        attachment_context = await build_attachment_context(attachment_ids, user["id"], provider)
        thread_id = payload.thread_id
        query = _query_with_history(
            _query_with_attachments(payload.query, attachment_context),
            _load_history_context(user["id"], thread_id),
        )
        final = await workflow_service.run(
            query=query,
            user_id=str(user["id"]),
            thread_id=payload.thread_id,
            tenant_id=payload.tenant_id,
            max_iterations=payload.max_iterations,
            enable_memory=payload.enable_memory,
            provider=provider,
        )
        _save_turn(user["id"], thread_id, payload.query, final)
        return ResearchResponse(
            query=payload.query,
            user_id=payload.user_id,
            thread_id=payload.thread_id,
            tenant_id=payload.tenant_id,
            final=final,
        )
    finally:
        delete_attachments(attachment_ids, user["id"])


@router.post("/stream")
async def stream_research(
    payload: ResearchRequest,
    workflow_service: WorkflowService = Depends(get_workflow_service),
    user: dict = Depends(current_user),
) -> StreamingResponse:
    provider = active_provider_for(user["id"])
    provider = _request_provider(provider, payload)
    history_context = _load_history_context(user["id"], payload.thread_id)

    async def event_stream():
        attachment_ids = list(payload.attachment_ids or [])
        try:
            if attachment_ids:
                status_event = {"type": "status", "message": "正在读取你上传的附件"}
                yield f"data: {json.dumps(status_event, ensure_ascii=False)}\n\n"
                try:
                    attachment_context = await build_attachment_context(attachment_ids, user["id"], provider)
                except Exception as exc:
                    error_event = {"type": "error", "message": getattr(exc, "detail", str(exc))}
                    yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
                    return
                complete_event = {"type": "status", "message": "附件已加入本轮研究上下文"}
                yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"
            else:
                attachment_context = ""
            start_event = {"type": "status", "message": "任务已接收，正在初始化多智能体链路"}
            yield f"data: {json.dumps(start_event, ensure_ascii=False)}\n\n"
            async for event in workflow_service.stream_events(
                query=_query_with_history(
                    _query_with_attachments(payload.query, attachment_context),
                    history_context,
                ),
                user_id=str(user["id"]),
                thread_id=payload.thread_id,
                tenant_id=payload.tenant_id,
                max_iterations=payload.max_iterations,
                enable_memory=payload.enable_memory,
                provider=provider,
            ):
                if event.get("type") == "final":
                    _save_turn(user["id"], payload.thread_id, payload.query, str(event.get("final", "")))
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        finally:
            delete_attachments(attachment_ids, user["id"])

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _request_provider(provider: dict, payload: ResearchRequest) -> dict:
    """Apply conversation-only model settings without changing saved defaults."""
    selected = dict(provider)
    if payload.model and payload.model.strip():
        selected["model"] = payload.model.strip()
    selected["reasoning_effort"] = payload.reasoning_effort or "auto"
    return selected


def _query_with_attachments(query: str, attachment_context: str) -> str:
    clean_query = query.strip() or "请分析我上传的资料，并提炼关键结论。"
    if not attachment_context:
        return clean_query
    return (
        f"{clean_query}\n\n"
        "以下是用户本轮主动上传的资料。请将其作为一手输入，结合用户问题进行分析；"
        "如果资料不足以支撑结论，请明确说明。\n\n"
        f"{attachment_context}"
    )
