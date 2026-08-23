from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ResearchRequest(BaseModel):
    query: str = Field(default="", max_length=20_000)
    user_id: str = Field(default="default_user", min_length=1)
    thread_id: str = Field(default="default_thread", min_length=1)
    tenant_id: str = Field(default="default_tenant", min_length=1)
    max_iterations: int | None = Field(default=None, ge=1, le=6)
    enable_memory: bool | None = None
    attachment_ids: list[str] = Field(default_factory=list, max_length=5)
    model: str | None = Field(default=None, max_length=160)
    reasoning_effort: Literal["auto", "low", "medium", "high", "xhigh"] = "auto"

    @model_validator(mode="after")
    def require_query_or_attachment(self) -> "ResearchRequest":
        if not self.query.strip() and not self.attachment_ids:
            raise ValueError("请输入问题或上传至少一个附件")
        return self


class ResearchResponse(BaseModel):
    query: str
    user_id: str
    thread_id: str
    tenant_id: str
    final: str


class ConversationMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class ConversationResponse(BaseModel):
    thread_id: str
    title: str
    updated_at: str
