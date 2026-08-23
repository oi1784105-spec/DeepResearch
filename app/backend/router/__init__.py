from .health_router import router as health_router
from .research_router import router as research_router
from .auth_router import router as auth_router
from .provider_router import router as provider_router
from .attachment_router import router as attachment_router
from .voice_router import router as voice_router

__all__ = ["health_router", "research_router", "auth_router", "provider_router", "attachment_router", "voice_router"]
