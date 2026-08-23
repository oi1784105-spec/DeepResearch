"""Provider-independent text-to-speech service.

The agent never imports a concrete TTS SDK. Providers are selected through
environment variables and the endpoint streams their audio response through
the backend so API keys never reach the browser.
"""

from __future__ import annotations

import html
import os
import re
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_PATH = _PROJECT_ROOT / ".env"
if _ENV_PATH.exists():
    # Keep TTS configuration consistent even when the workflow module is not imported first.
    load_dotenv(_ENV_PATH, override=False)


class TTSUnavailableError(RuntimeError):
    """Raised when TTS is not configured or an upstream provider fails."""


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def tts_provider() -> str:
    return _env("TTS_PROVIDER", "browser").lower()


def tts_enabled() -> bool:
    return (
        tts_provider() in {"elevenlabs", "fish", "fish_audio"}
        and bool(_env("TTS_API_KEY"))
        and bool(_env("TTS_VOICE_ID"))
    )


def tts_public_config() -> dict[str, str | bool]:
    provider = tts_provider()
    return {
        "enabled": tts_enabled(),
        "provider": provider if provider in {"elevenlabs", "fish", "fish_audio"} else "browser",
        "voice": _env("TTS_VOICE_ID", ""),
    }


def optimize_speech_text(value: str, max_chars: int = 9000) -> str:
    """Turn report-like LLM output into concise spoken Chinese.

    This intentionally preserves facts and only removes visual markup,
    internal workflow phrases, and overly long sentence structure.
    """

    text = html.unescape(str(value or ""))
    text = re.sub(r"```[\s\S]*?```", "代码内容已省略。", text)
    text = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    # Citations and execution appendices are useful on screen, but make poor speech.
    text = re.split(
        r"(?im)^\s*##\s*(?:参考资料|引用列表|来源清单|规划与检索明细)\b",
        text,
        maxsplit=1,
    )[0]
    text = re.sub(r"\[[A-Z]+\d+_\d+-\d+\]", "", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*[*_`>]+\s*", " ", text)
    text = re.sub(r"(?:正在调用|开始执行|工具返回|调用 search 工具|开始执行第二个 Agent)[^。！？!?\n]*[。！？!?]?", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return ""

    # Add natural boundaries for long written sentences without changing wording.
    pieces = re.split(r"(?<=[。！？!?；;])\s*|\n+", text)
    normalized: list[str] = []
    for piece in pieces:
        piece = piece.strip(" ，,、")
        if not piece:
            continue
        if len(piece) <= 36:
            normalized.append(piece)
            continue
        clauses = re.split(r"(?<=[，,：:])\s*", piece)
        current = ""
        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue
            candidate = f"{current}{clause}" if current else clause
            if current and len(candidate) > 22:
                normalized.append(current.rstrip("，,：:"))
                current = clause
            else:
                current = candidate
        if current:
            normalized.append(current)
    return "\n".join(normalized)[:max_chars]


def _provider_request(provider: str, text: str) -> tuple[str, dict[str, str], dict]:
    key = _env("TTS_API_KEY")
    voice = _env("TTS_VOICE_ID")
    if not key or not voice:
        raise TTSUnavailableError("TTS 尚未配置 API Key 或音色 ID")
    if provider == "elevenlabs":
        base = _env("TTS_BASE_URL", "https://api.elevenlabs.io")
        try:
            stability = float(_env("TTS_STABILITY", "0.52"))
            similarity = float(_env("TTS_SIMILARITY", "0.82"))
            style = float(_env("TTS_STYLE", "0.12"))
        except ValueError as exc:
            raise TTSUnavailableError("TTS 音色参数必须是数字") from exc
        return (
            f"{base.rstrip('/')}/v1/text-to-speech/{voice}/stream?output_format=mp3_44100_128",
            {"xi-api-key": key, "accept": "audio/mpeg", "content-type": "application/json"},
            {
                "text": text,
                "model_id": _env("TTS_MODEL", "eleven_multilingual_v2"),
                "voice_settings": {
                    "stability": min(max(stability, 0.0), 1.0),
                    "similarity_boost": min(max(similarity, 0.0), 1.0),
                    "style": min(max(style, 0.0), 1.0),
                    "use_speaker_boost": True,
                },
            },
        )
    if provider in {"fish", "fish_audio"}:
        base = _env("TTS_BASE_URL", "https://api.fish.audio")
        return (
            f"{base.rstrip('/')}/v1/tts",
            {"Authorization": f"Bearer {key}", "accept": "audio/mpeg", "content-type": "application/json"},
            {
                "text": text,
                "reference_id": voice,
                "format": "mp3",
                "latency": "balanced",
            },
        )
    raise TTSUnavailableError("当前未启用云端 TTS")


async def stream_speech(text: str) -> AsyncIterator[bytes]:
    optimized = optimize_speech_text(text, max_chars=1800)
    if not optimized:
        raise TTSUnavailableError("没有可朗读的内容")
    provider = tts_provider()
    url, headers, payload = _provider_request(provider, optimized)
    timeout = httpx.Timeout(
        connect=float(_env("TTS_CONNECT_TIMEOUT", "8")),
        read=float(_env("TTS_READ_TIMEOUT", "45")),
        write=15.0,
        pool=8.0,
    )
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                if response.status_code >= 400:
                    detail = (await response.aread()).decode("utf-8", errors="replace")[:400]
                    raise TTSUnavailableError(f"TTS 服务返回 {response.status_code}: {detail}")
                async for chunk in response.aiter_bytes(16_384):
                    if chunk:
                        yield chunk
    except (httpx.HTTPError, TimeoutError) as exc:
        raise TTSUnavailableError(f"TTS 服务暂时不可用: {exc}") from exc


async def synthesize_speech(text: str) -> tuple[bytes, str]:
    data = bytearray()
    async for chunk in stream_speech(text):
        data.extend(chunk)
    return bytes(data), "audio/mpeg"
