import asyncio
import json
import re
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Depends, HTTPException

from backend.database import db
from backend.deps import current_user
from backend.schemas.provider import (
    ProviderInput,
    ProviderModelsResponse,
    ProviderResponse,
    ProviderTestResponse,
    ProviderUpdate,
)
from backend.security import decrypt_api_key, encrypt_api_key
from backend.service import get_workflow_service


router = APIRouter(prefix="/api/v1/providers", tags=["providers"])


def _public(row: dict) -> ProviderResponse:
    try:
        available_models = json.loads(row.get("available_models") or "[]")
    except (TypeError, ValueError):
        available_models = []
    if not isinstance(available_models, list):
        available_models = []
    return ProviderResponse(
        id=row["id"], name=row["name"], provider_type=row["provider_type"], protocol=row["protocol"],
        endpoint=row["endpoint"], model=row["model"], api_version=row["api_version"],
        reasoning_effort=row["reasoning_effort"] or "auto", active=bool(row["active"]),
        available_models=[str(item) for item in available_models if str(item).strip()],
    )


def _endpoint(endpoint: str, suffix: str) -> str:
    clean = endpoint.rstrip("/")
    # Accept both a base URL (/v1) and a copied operation URL
    # (/v1/chat/completions or /v1/models) from provider dashboards.
    for operation in ("/chat/completions", "/messages", "/models"):
        if clean.endswith(operation):
            clean = clean[: -len(operation)].rstrip("/")
            break
    base = clean + "/"
    return urljoin(base, suffix.lstrip("/"))


def _upstream_error(response: httpx.Response) -> str:
    """Return a useful, key-free upstream error for the configuration page."""
    detail = ""
    try:
        body = response.json()
        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                detail = str(error.get("message") or error.get("code") or "")
            elif error:
                detail = str(error)
            detail = detail or str(body.get("message") or body.get("detail") or "")
    except ValueError:
        detail = response.text.strip()[:240]
    detail = re.sub(r"(?i)(api[\s_-]*key)\s*[:=]\s*[^,\s]+", r"\1: [redacted]", detail)
    detail = re.sub(r"\bsk-[A-Za-z0-9_-]{6,}\b", "[redacted]", detail)
    detail = re.sub(r"\*{2,}[A-Za-z0-9_-]{2,}", "[redacted]", detail)
    suffix = f"：{detail}" if detail else ""
    return f"上游接口返回 HTTP {response.status_code}{suffix}"


async def _test_provider(payload: ProviderInput) -> ProviderTestResponse:
    endpoint = str(payload.endpoint).rstrip("/")
    headers = {"Authorization": f"Bearer {payload.api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        if payload.protocol == "openai_chat":
            response = await client.post(_endpoint(endpoint, "/chat/completions"), headers=headers, json={"model": payload.model, "messages": [{"role": "user", "content": "Reply with OK"}], "max_tokens": 8, **({"reasoning_effort": payload.reasoning_effort} if payload.reasoning_effort != "auto" else {})})
            if response.status_code >= 400:
                return ProviderTestResponse(ok=False, message=_upstream_error(response))
            try:
                models = await _discover_models(payload, client)
                return ProviderTestResponse(ok=True, message="Chat Completions 连接成功", models=models)
            except RuntimeError as exc:
                return ProviderTestResponse(ok=True, message=f"Chat Completions 连接成功；模型列表获取失败：{exc}", models=[])
        if payload.protocol == "anthropic_messages":
            headers = {"x-api-key": payload.api_key, "anthropic-version": payload.api_version or "2023-06-01", "content-type": "application/json"}
            response = await client.post(_endpoint(endpoint, "/messages"), headers=headers, json={"model": payload.model, "max_tokens": 8, "messages": [{"role": "user", "content": "Reply with OK"}]})
            if response.status_code >= 400:
                return ProviderTestResponse(ok=False, message=_upstream_error(response))
            return ProviderTestResponse(ok=True, message="Anthropic Messages 连接成功（该协议不提供统一模型列表）")
        if payload.protocol == "gemini_generate":
            response = await client.post(f"{endpoint}/models/{payload.model}:generateContent", params={"key": payload.api_key}, json={"contents": [{"parts": [{"text": "Reply with OK"}]}]})
            if response.status_code >= 400:
                return ProviderTestResponse(ok=False, message=_upstream_error(response))
            try:
                models = await _discover_models(payload, client)
                return ProviderTestResponse(ok=True, message="Gemini Generate Content 连接成功", models=models)
            except RuntimeError as exc:
                return ProviderTestResponse(ok=True, message=f"Gemini 连接成功；模型列表获取失败：{exc}", models=[])
    return ProviderTestResponse(ok=False, message="不支持的 API 协议")


async def _discover_models(payload: ProviderInput, client: httpx.AsyncClient | None = None) -> list[str]:
    """Discover model ids without ever returning or logging the API key."""
    endpoint = str(payload.endpoint).rstrip("/")
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=20, follow_redirects=True)
    assert client is not None
    try:
        if payload.protocol == "openai_chat":
            response = await client.get(
                _endpoint(endpoint, "/models"),
                headers={"Authorization": f"Bearer {payload.api_key}"},
            )
            if response.status_code >= 400:
                raise RuntimeError(_upstream_error(response))
            body = response.json()
            values = body.get("data", []) if isinstance(body, dict) else []
            return sorted({str(item.get("id", "")).strip() for item in values if isinstance(item, dict) and item.get("id")})[:200]
        if payload.protocol == "gemini_generate":
            response = await client.get(f"{endpoint}/models", params={"key": payload.api_key})
            if response.status_code >= 400:
                raise RuntimeError(_upstream_error(response))
            body = response.json()
            values = body.get("models", []) if isinstance(body, dict) else []
            return sorted({str(item.get("name", "")).removeprefix("models/").strip() for item in values if isinstance(item, dict) and item.get("name")})[:200]
        return []
    finally:
        if own_client:
            await client.aclose()


@router.get("", response_model=list[ProviderResponse])
def list_providers(user: dict = Depends(current_user)) -> list[ProviderResponse]:
    with db() as conn:
        rows = conn.execute("SELECT * FROM providers WHERE user_id = ? ORDER BY updated_at DESC", (user["id"],)).fetchall()
    return [_public(dict(row)) for row in rows]


@router.post("/test", response_model=ProviderTestResponse)
async def test_provider(payload: ProviderInput, user: dict = Depends(current_user)) -> ProviderTestResponse:
    try:
        return await _test_provider(payload)
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        return ProviderTestResponse(ok=False, message=f"连接失败：{exc}")


@router.post("/models", response_model=ProviderModelsResponse)
async def discover_provider_models(payload: ProviderInput, user: dict = Depends(current_user)) -> ProviderModelsResponse:
    try:
        models = await _discover_models(payload)
        if models:
            return ProviderModelsResponse(ok=True, message=f"已获取 {len(models)} 个模型", models=models)
        if payload.protocol == "anthropic_messages":
            return ProviderModelsResponse(ok=True, message="Anthropic 接口没有统一模型列表，请手动填写模型 ID", models=[])
        return ProviderModelsResponse(ok=False, message="接口未返回模型列表，请检查 Endpoint、Key 或手动填写模型 ID", models=[])
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        return ProviderModelsResponse(ok=False, message=f"获取模型失败：{exc}", models=[])


@router.get("/{provider_id}/models", response_model=ProviderModelsResponse)
async def discover_saved_provider_models(provider_id: int, user: dict = Depends(current_user)) -> ProviderModelsResponse:
    with db() as conn:
        row = conn.execute("SELECT * FROM providers WHERE id = ? AND user_id = ?", (provider_id, user["id"])).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Provider 不存在")
    record = dict(row)
    payload = ProviderInput(
        name=record["name"], provider_type=record["provider_type"], protocol=record["protocol"],
        endpoint=record["endpoint"], api_key=decrypt_api_key(record["api_key_encrypted"]), model=record["model"],
        api_version=record["api_version"], reasoning_effort=record.get("reasoning_effort") or "auto",
    )
    result = await discover_provider_models(payload, user)
    if result.models:
        with db() as conn:
            conn.execute(
                "UPDATE providers SET available_models = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
                (json.dumps(result.models, ensure_ascii=False), provider_id, user["id"]),
            )
    return result


@router.post("", response_model=ProviderResponse, status_code=201)
def create_provider(payload: ProviderInput, user: dict = Depends(current_user)) -> ProviderResponse:
    with db() as conn:
        if payload.active:
            conn.execute("UPDATE providers SET active = 0 WHERE user_id = ?", (user["id"],))
        cursor = conn.execute(
            "INSERT INTO providers(user_id, name, provider_type, protocol, endpoint, api_key_encrypted, model, api_version, reasoning_effort, available_models, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user["id"], payload.name.strip(), payload.provider_type, payload.protocol, str(payload.endpoint).rstrip("/"), encrypt_api_key(payload.api_key), payload.model.strip(), payload.api_version, payload.reasoning_effort, json.dumps(payload.available_models, ensure_ascii=False), int(payload.active)),
        )
        row = conn.execute("SELECT * FROM providers WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _public(dict(row))


@router.put("/{provider_id}/activate", response_model=ProviderResponse)
def activate_provider(provider_id: int, user: dict = Depends(current_user)) -> ProviderResponse:
    with db() as conn:
        row = conn.execute("SELECT * FROM providers WHERE id = ? AND user_id = ?", (provider_id, user["id"])).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Provider 不存在")
        conn.execute("UPDATE providers SET active = 0 WHERE user_id = ?", (user["id"],))
        conn.execute("UPDATE providers SET active = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (provider_id,))
        row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    return _public(dict(row))


@router.put("/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: int, payload: ProviderUpdate, user: dict = Depends(current_user)) -> ProviderResponse:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM providers WHERE id = ? AND user_id = ?",
            (provider_id, user["id"]),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Provider 不存在")
        if payload.active:
            conn.execute("UPDATE providers SET active = 0 WHERE user_id = ?", (user["id"],))
        encrypted_key = encrypt_api_key(payload.api_key) if payload.api_key else row["api_key_encrypted"]
        conn.execute(
            """UPDATE providers
               SET name = ?, provider_type = ?, protocol = ?, endpoint = ?,
                   api_key_encrypted = ?, model = ?, api_version = ?, reasoning_effort = ?, available_models = ?,
                   active = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (
                payload.name.strip(), payload.provider_type, payload.protocol,
                str(payload.endpoint).rstrip("/"), encrypted_key, payload.model.strip(),
                payload.api_version, payload.reasoning_effort, json.dumps(payload.available_models, ensure_ascii=False), int(payload.active), provider_id, user["id"],
            ),
        )
        updated = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    get_workflow_service().invalidate_provider(provider_id)
    return _public(dict(updated))


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: int, user: dict = Depends(current_user)) -> None:
    with db() as conn:
        row = conn.execute("SELECT id FROM providers WHERE id = ? AND user_id = ?", (provider_id, user["id"])).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Provider 不存在")
        conn.execute("DELETE FROM providers WHERE id = ? AND user_id = ?", (provider_id, user["id"]))
    get_workflow_service().invalidate_provider(provider_id)
