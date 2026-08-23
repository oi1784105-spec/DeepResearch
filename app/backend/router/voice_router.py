from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.deps import current_user
from backend.service.voice_service import (
    TTSUnavailableError,
    optimize_speech_text,
    stream_speech,
    tts_public_config,
)


router = APIRouter(prefix="/api/v1/tts", tags=["tts"])


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=9000)


@router.get("/config")
def config() -> dict[str, str | bool]:
    return tts_public_config()


@router.post("/synthesize")
async def synthesize(payload: TTSRequest, user: dict = Depends(current_user)) -> StreamingResponse:
    del user
    if not tts_public_config()["enabled"]:
        raise HTTPException(status_code=503, detail="云端 TTS 未配置，已使用浏览器语音回退")
    optimized = optimize_speech_text(payload.text)
    if not optimized:
        raise HTTPException(status_code=422, detail="没有可朗读的文本")

    async def audio_stream():
        try:
            async for chunk in stream_speech(optimized):
                yield chunk
        except TTSUnavailableError as exc:
            # The browser treats a failed audio request as a signal to use its fallback.
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return StreamingResponse(
        audio_stream(),
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-store", "X-TTS-Provider": str(tts_public_config()["provider"])},
    )
