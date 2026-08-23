import asyncio
import re
from threading import Lock, Thread
from typing import AsyncIterator, Callable

from mult_agents.config import AppConfig
from mult_agents.graph import build_app as build_workflow_app
from mult_agents.main import build_agents, build_checkpointer, build_memory_manager
from mult_agents.nodes import reset_speech_delta_emitter, set_speech_delta_emitter
from mult_agents.state import create_initial_state
from backend.security import decrypt_api_key
from langgraph.checkpoint.memory import InMemorySaver


def _safe_error_message(error: Exception) -> str:
    """Remove API key fragments before an upstream error reaches the browser."""
    message = str(error)
    message = re.sub(
        r"(?i)\b(?:sk|pk)-[A-Za-z0-9_-]{3,}(?:\*+[A-Za-z0-9_-]*)?\b",
        "[redacted]",
        message,
    )
    message = re.sub(
        r"(?i)(api[\s_-]*key)\s*[:=]\s*[^,\s}]+",
        r"\1=[redacted]",
        message,
    )
    return message[:1200]


class WorkflowService:
    def __init__(self, config_path: str):
        self._config_path = config_path
        self._lock = Lock()
        self._initialized = False
        self._base_config: AppConfig | None = None
        self._memory_manager = None
        self._app = None
        self._provider_apps: dict[int, tuple[tuple[str, str, str, str, str, str], object]] = {}

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            # The web app stores the active user's encrypted Provider key separately.
            # A global LLM key is optional here and is only needed by legacy CLI paths.
            base_config = AppConfig.from_file(self._config_path, require_api_key=False)
            self._memory_manager = build_memory_manager(base_config)
            self._app = None
            if base_config.api_key:
                agents = build_agents(base_config.model, base_config.api_key, base_config)
                checkpointer = build_checkpointer(base_config)
                self._app = build_workflow_app(agents, checkpointer)
            self._base_config = base_config
            self._initialized = True

    def _app_for_provider(self, provider: dict) -> object:
        if self._base_config is None:
            raise RuntimeError("service not initialized")
        fingerprint = (
            provider["provider_type"], provider["protocol"], provider["endpoint"], provider["model"],
            provider["api_key_encrypted"], provider.get("reasoning_effort") or "auto",
        )
        cached = self._provider_apps.get(int(provider["id"]))
        if cached and cached[0] == fingerprint:
            return cached[1]
        provider_type = provider["provider_type"]
        if provider["protocol"] == "openai_chat":
            provider_type = "openai_compatible"
        config = self._base_config.with_overrides(
            llm_provider=provider_type,
            api_key=decrypt_api_key(provider["api_key_encrypted"]),
            base_url=provider["endpoint"],
            model=provider["model"],
            reasoning_effort=provider.get("reasoning_effort") or "auto",
            enable_memory=False,
            checkpointer_backend="memory",
        )
        agents = build_agents(config.model, config.api_key, config)
        app = build_workflow_app(agents, InMemorySaver())
        self._provider_apps[int(provider["id"])] = (fingerprint, app)
        return app

    def invalidate_provider(self, provider_id: int) -> None:
        """Drop a provider app so its decrypted API key is no longer retained by this service."""
        with self._lock:
            self._provider_apps.pop(int(provider_id), None)

    def clear_provider_cache(self) -> None:
        """Drop all cached provider apps, including their model clients and API keys."""
        with self._lock:
            self._provider_apps.clear()

    def _build_runtime_config(
        self,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
    ) -> AppConfig:
        if self._base_config is None:
            raise RuntimeError("service not initialized")
        overrides = {
            "user_id": user_id,
            "thread_id": thread_id,
            "tenant_id": tenant_id,
            "max_iterations": max_iterations if max_iterations is not None else self._base_config.max_iterations,
        }
        if enable_memory is not None:
            overrides["enable_memory"] = enable_memory
        return self._base_config.with_overrides(**overrides)

    def _run_sync(
        self,
        query: str,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
        provider: dict,
    ) -> tuple[str, str]:
        self._ensure_initialized()
        runtime_config = self._build_runtime_config(
            user_id=user_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
        )
        memory_context = ""
        if self._memory_manager and runtime_config.enable_memory:
            memory_context = self._memory_manager.build_personalized_prompt_context(
                user_id=runtime_config.user_id,
                thread_id=runtime_config.thread_id,
                query=query,
                tenant_id=runtime_config.tenant_id,
                max_memories=runtime_config.memory_top_k,
            )
        state = create_initial_state(
            query=query,
            max_iterations=runtime_config.max_iterations,
            user_id=runtime_config.user_id,
            tenant_id=runtime_config.tenant_id,
            memory_context=memory_context,
        )
        result = self._app_for_provider(provider).invoke(
            state,
            {"configurable": {"thread_id": runtime_config.thread_id}},
        )
        final = result.get("final", "")
        route = str(result.get("intent", "multiagent"))
        if self._memory_manager and runtime_config.enable_memory:
            self._memory_manager.persist_turn(
                tenant_id=runtime_config.tenant_id,
                user_id=runtime_config.user_id,
                thread_id=runtime_config.thread_id,
                query=query,
                answer=final,
            )
        return final, route

    @staticmethod
    def _node_message(node_name: str) -> str:
        mapping = {
            "intent": "Intent Router 正在识别问题意图",
            "direct_answer": "Direct Responder 正在快速作答",
            "plan": "Planner 正在拆解问题",
            "web_search": "Web Scout 正在检索网络证据",
            "local_rag": "Local Scout 正在检索本地知识库",
            "deep_dive": "Evidence Judge 正在进行证据裁判",
            "analyze": "Analyst 正在生成结论",
            "reflect": "Reflect 正在生成补搜计划",
            "write": "Writer 正在撰写最终报告",
        }
        return mapping.get(node_name, f"{node_name} 正在执行")

    def _run_sync_with_events(
        self,
        query: str,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
        provider: dict,
        emit: Callable[[dict], None],
    ) -> tuple[str, str]:
        self._ensure_initialized()
        runtime_config = self._build_runtime_config(
            user_id=user_id,
            thread_id=thread_id,
            tenant_id=tenant_id,
            max_iterations=max_iterations,
            enable_memory=enable_memory,
        )
        memory_context = ""
        if self._memory_manager and runtime_config.enable_memory:
            memory_context = self._memory_manager.build_personalized_prompt_context(
                user_id=runtime_config.user_id,
                thread_id=runtime_config.thread_id,
                query=query,
                tenant_id=runtime_config.tenant_id,
                max_memories=runtime_config.memory_top_k,
            )
        state = create_initial_state(
            query=query,
            max_iterations=runtime_config.max_iterations,
            user_id=runtime_config.user_id,
            tenant_id=runtime_config.tenant_id,
            memory_context=memory_context,
        )
        final = ""
        route = "multiagent"
        config = {"configurable": {"thread_id": runtime_config.thread_id}}
        app = self._app_for_provider(provider)
        for update in app.stream(state, config, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node_name, node_output in update.items():
                emit({"type": "phase", "node": node_name, "message": self._node_message(str(node_name))})
                if isinstance(node_output, dict):
                    if node_name == "intent":
                        detected = str(node_output.get("intent", route)).strip().lower()
                        if detected in {"direct", "multiagent"}:
                            route = detected
                    value = node_output.get("final")
                    if value:
                        final = str(value)
        if not final:
            result = app.invoke(state, config)
            final = str(result.get("final", ""))
            route = str(result.get("intent", route)).strip().lower()
        if self._memory_manager and runtime_config.enable_memory:
            self._memory_manager.persist_turn(
                tenant_id=runtime_config.tenant_id,
                user_id=runtime_config.user_id,
                thread_id=runtime_config.thread_id,
                query=query,
                answer=final,
            )
        return final, route

    async def run(
        self,
        query: str,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
        provider: dict,
    ) -> str:
        final, _ = await asyncio.to_thread(
            self._run_sync,
            query,
            user_id,
            thread_id,
            tenant_id,
            max_iterations,
            enable_memory,
            provider,
        )
        return final

    async def run_with_route(
        self,
        query: str,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
        provider: dict,
    ) -> tuple[str, str]:
        return await asyncio.to_thread(
            self._run_sync,
            query,
            user_id,
            thread_id,
            tenant_id,
            max_iterations,
            enable_memory,
            provider,
        )

    async def stream_events(
        self,
        query: str,
        user_id: str,
        thread_id: str,
        tenant_id: str,
        max_iterations: int | None,
        enable_memory: bool | None,
        provider: dict,
    ) -> AsyncIterator[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            asyncio.run_coroutine_threadsafe(queue.put(event), loop)

        def worker() -> None:
            emitter_token = set_speech_delta_emitter(
                lambda node, text: emit({"type": "speech_delta", "node": node, "text": text})
            )
            try:
                final, route = self._run_sync_with_events(
                    query=query,
                    user_id=user_id,
                    thread_id=thread_id,
                    tenant_id=tenant_id,
                    max_iterations=max_iterations,
                    enable_memory=enable_memory,
                    provider=provider,
                    emit=emit,
                )
                emit({"type": "route", "message": "已走直接回答路径" if route == "direct" else "已走多智能体研究路径"})
                emit(
                    {
                        "type": "final",
                        "query": query,
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "tenant_id": tenant_id,
                        "final": final,
                    }
                )
            except Exception as exc:
                emit({"type": "error", "message": _safe_error_message(exc)})
            finally:
                reset_speech_delta_emitter(emitter_token)
                emit({"type": "__done__"})

        Thread(target=worker, daemon=True).start()
        while True:
            event = await queue.get()
            if event.get("type") == "__done__":
                break
            yield event
