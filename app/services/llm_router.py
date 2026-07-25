"""
LLM Router — Universal LLMProvider adapter.

WORK LAPTOP NOTE (see MIGRATION_GUIDE.md):
  litellm cannot be installed because it requires Rust (maturin) and rustup
  download fails due to corporate SSL certificate inspection.
  The LLMProvider class below is backed by the openai SDK for now.
  Every provider-specific block is dual-tracked with comments:

    # OPENAI ONLY — delete these lines on personal laptop
    # LITELLM     — uncomment these lines on personal laptop

  The public interface (call_llm / stream_llm / LLMRouterResult) is
  provider-agnostic. proxy.py and every other caller never need to change.

Migration is a 4-step surgery inside this file only:
  1. pip install litellm
  2. Uncomment every # LITELLM line
  3. Delete every # OPENAI ONLY line
  4. Delete _make_client() helper and the openai/httpx imports
"""
import time
from typing import AsyncGenerator

# OPENAI ONLY — delete this import block on personal laptop
import httpx
from openai import AsyncOpenAI, RateLimitError, APIStatusError
# OPENAI ONLY — end

# LITELLM — uncomment on personal laptop (and delete the openai block above)
# import litellm
# from litellm.exceptions import RateLimitError, APIError as APIStatusError
# LITELLM — end

from app.config import get_settings
from app.db.schemas import ChatCompletionRequest

settings = get_settings()

# Cost per 1K tokens (USD) — rough estimates; provider-agnostic
COST_PER_1K: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini":      {"input": 0.00015,  "output": 0.0006},
    "gpt-4o":           {"input": 0.005,    "output": 0.015},
    # Google Gemini
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
    "gemini-1.5-pro":   {"input": 0.00125,  "output": 0.005},
    # Cerebras (wafer-scale — very cheap per token)
    "llama3.1-8b":      {"input": 0.0001,   "output": 0.0001},
    "llama3.1-70b":     {"input": 0.00085,  "output": 0.0012},
    "llama-3.3-70b":    {"input": 0.00085,  "output": 0.0012},
    "gpt-oss-120b":     {"input": 0.0009,   "output": 0.0009},
    "gemma-4-31b":      {"input": 0.0002,   "output": 0.0004},
    "zai-glm-4.7":      {"input": 0.0005,   "output": 0.0005},
}


def _strip_provider_prefix(model: str) -> str:
    """'gemini/gemini-1.5-flash' → 'gemini-1.5-flash'. No-op if no prefix."""
    if "/" in model:
        return model.split("/", 1)[1]
    return model


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    clean = _strip_provider_prefix(model)
    # UNKNOWN_MODEL_FALLBACK: model not in COST_PER_1K — add it to keep
    # Superset cost charts accurate. Defaults are deliberately high to make
    # missing entries visible in dashboards rather than silently cheap.
    rates = COST_PER_1K.get(clean, {"input": 0.001, "output": 0.002})
    return (prompt_tokens / 1000 * rates["input"]) + (completion_tokens / 1000 * rates["output"])


class LLMRouterResult:
    """Provider-agnostic result container returned by LLMProvider.call()."""

    def __init__(
        self,
        content: str,
        model_used: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        ttft_ms: float | None,
        total_latency_ms: float,
        was_fallback: bool,
        cost_usd: float,
    ):
        self.content = content
        self.model_used = model_used
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.ttft_ms = ttft_ms
        self.total_latency_ms = total_latency_ms
        self.was_fallback = was_fallback
        self.cost_usd = cost_usd


class LLMProvider:
    """
    Universal LLM adapter.

    Currently backed by the openai SDK (work-laptop constraint).
    Switching to litellm on a personal laptop requires changes only inside
    this class — see the # OPENAI ONLY / # LITELLM comment pairs.

    Public API (never changes regardless of backend):
      await provider.call(request)   -> LLMRouterResult
      provider.stream(request)       -> AsyncGenerator[str, None]
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    # ------------------------------------------------------------------
    # OPENAI ONLY — delete this entire method on personal laptop
    # (litellm is provider-agnostic by model string; no client factory needed)
    def _make_client(self, model: str) -> "AsyncOpenAI":
        """
        Returns an AsyncOpenAI client pointed at the correct endpoint.

        WORK LAPTOP NOTE: verify=False on httpx disables SSL cert validation,
        required behind the corporate SSL inspection proxy.
        Remove verify=False on a personal laptop.
        """
        if "gemini" in model:
            return AsyncOpenAI(
                api_key=self._settings.gemini_api_key or "dummy",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                http_client=httpx.AsyncClient(verify=False),  # MIGRATION: remove verify=False
            )
        return AsyncOpenAI(
            api_key=self._settings.openai_api_key or "dummy",
            base_url=self._settings.openai_base_url,          # reads OPENAI_BASE_URL from .env
            http_client=httpx.AsyncClient(verify=False),      # MIGRATION: remove verify=False
        )
    # OPENAI ONLY — end

    async def call(self, request: ChatCompletionRequest, model_override: str | None = None) -> LLMRouterResult:
        """
        Calls the primary model; falls back to secondary on 429 / 503.
        Returns a fully-resolved LLMRouterResult (non-streaming).

        model_override: when set (e.g. by smart routing), replaces primary_model.
        When None, behavior is identical to today.
        """
        messages = [m.model_dump(exclude_none=True) for m in request.messages]
        primary = model_override or self._settings.primary_model
        models_to_try = [primary, self._settings.fallback_model]

        last_exc: Exception | None = None
        for idx, model in enumerate(models_to_try):
            # Gemini's own API wants "gemini-1.5-flash" (no prefix).
            # OpenRouter wants the full ID e.g. "meta-llama/llama-3.2-3b-instruct:free".
            model_id = _strip_provider_prefix(model) if "gemini" in model else model
            t_start = time.perf_counter()
            try:
                # OPENAI ONLY — delete this block on personal laptop -----------
                client = self._make_client(model)
                response = await client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                total_latency_ms = (time.perf_counter() - t_start) * 1000
                usage = response.usage
                content = response.choices[0].message.content or ""
                pt = usage.prompt_tokens if usage else 0
                ct = usage.completion_tokens if usage else 0
                tt = usage.total_tokens if usage else 0
                # OPENAI ONLY — end -------------------------------------------

                # LITELLM — uncomment on personal laptop (delete block above) --
                # response = await litellm.acompletion(
                #     model=model,
                #     messages=messages,
                #     temperature=request.temperature,
                #     max_tokens=request.max_tokens,
                # )
                # total_latency_ms = (time.perf_counter() - t_start) * 1000
                # usage = response.usage
                # content = response.choices[0].message.content or ""
                # pt = usage.prompt_tokens if usage else 0
                # ct = usage.completion_tokens if usage else 0
                # tt = usage.total_tokens if usage else 0
                # LITELLM — end ------------------------------------------------

                return LLMRouterResult(
                    content=content,
                    model_used=model,
                    prompt_tokens=pt,
                    completion_tokens=ct,
                    total_tokens=tt,
                    ttft_ms=None,
                    total_latency_ms=total_latency_ms,
                    was_fallback=(idx > 0),
                    cost_usd=estimate_cost(model, pt, ct),
                )

            except RateLimitError as exc:
                last_exc = exc
                if idx < len(models_to_try) - 1:
                    continue
            except APIStatusError as exc:
                if exc.status_code in (404, 503, 502) and idx < len(models_to_try) - 1:
                    last_exc = exc
                    continue
                raise

        raise last_exc  # type: ignore[misc]

    async def stream(self, request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
        """Yields text chunks for streaming mode, with fallback on rate-limit."""
        messages = [m.model_dump(exclude_none=True) for m in request.messages]
        models_to_try = [self._settings.primary_model, self._settings.fallback_model]

        for idx, model in enumerate(models_to_try):
            model_id = _strip_provider_prefix(model) if "gemini" in model else model
            try:
                # OPENAI ONLY — delete this block on personal laptop -----------
                client = self._make_client(model)
                stream = await client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    stream=True,
                )
                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
                return
                # OPENAI ONLY — end -------------------------------------------

                # LITELLM — uncomment on personal laptop (delete block above) --
                # async for chunk in await litellm.acompletion(
                #     model=model,
                #     messages=messages,
                #     temperature=request.temperature,
                #     max_tokens=request.max_tokens,
                #     stream=True,
                # ):
                #     if chunk.choices and chunk.choices[0].delta.content:
                #         yield chunk.choices[0].delta.content
                # return
                # LITELLM — end ------------------------------------------------

            except RateLimitError:
                if idx < len(models_to_try) - 1:
                    continue
                raise
            except APIStatusError as exc:
                if exc.status_code in (404, 503, 502) and idx < len(models_to_try) - 1:
                    continue
                raise


# ---------------------------------------------------------------------------
# Module-level singleton + backward-compatible shims
#
# proxy.py imports call_llm and stream_llm directly. These thin wrappers
# mean proxy.py (and any other caller) never needs to know about LLMProvider.
# ---------------------------------------------------------------------------

_provider = LLMProvider()


async def call_llm(request: ChatCompletionRequest, model_override: str | None = None) -> LLMRouterResult:
    return await _provider.call(request, model_override=model_override)


async def stream_llm(request: ChatCompletionRequest) -> AsyncGenerator[str, None]:
    async for chunk in _provider.stream(request):
        yield chunk
