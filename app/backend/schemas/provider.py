from pydantic import BaseModel, Field, HttpUrl, field_validator


PROVIDER_TYPES = {"openai", "deepseek", "dashscope", "anthropic", "gemini", "custom"}
PROTOCOLS = {"openai_chat", "anthropic_messages", "gemini_generate"}
REASONING_EFFORTS = {"auto", "low", "medium", "high", "xhigh"}


class ProviderInput(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    provider_type: str = Field(min_length=1, max_length=30)
    protocol: str = Field(default="openai_chat", min_length=1, max_length=30)
    endpoint: HttpUrl
    api_key: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=160)
    api_version: str | None = Field(default=None, max_length=50)
    reasoning_effort: str = Field(default="auto", max_length=20)
    available_models: list[str] = Field(default_factory=list, max_length=200)
    active: bool = False

    @field_validator("provider_type")
    @classmethod
    def validate_provider_type(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in PROVIDER_TYPES:
            raise ValueError(f"provider_type 必须是: {', '.join(sorted(PROVIDER_TYPES))}")
        return value

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in PROTOCOLS:
            raise ValueError(f"protocol 必须是: {', '.join(sorted(PROTOCOLS))}")
        return value

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, value: str) -> str:
        value = value.lower().strip()
        if value not in REASONING_EFFORTS:
            raise ValueError(f"reasoning_effort 必须是: {', '.join(sorted(REASONING_EFFORTS))}")
        return value

    @field_validator("available_models")
    @classmethod
    def normalize_available_models(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            model = item.strip()
            if model and model not in cleaned:
                cleaned.append(model)
        return cleaned[:200]


class ProviderUpdate(ProviderInput):
    """Provider edit payload; omitting api_key keeps the encrypted key unchanged."""

    api_key: str | None = Field(default=None, max_length=500)

class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    protocol: str
    endpoint: str
    model: str
    api_version: str | None
    reasoning_effort: str = "auto"
    available_models: list[str] = Field(default_factory=list)
    active: bool
    has_api_key: bool = True


class ProviderTestResponse(BaseModel):
    ok: bool
    message: str
    models: list[str] = Field(default_factory=list)


class ProviderModelsResponse(BaseModel):
    ok: bool
    message: str
    models: list[str] = Field(default_factory=list)
