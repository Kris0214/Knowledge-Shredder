"""
LLM Provider Factory
====================
要新增供應商：
  1. 在 services/llm/ 下建立新的 provider 檔案（繼承 BaseLLMProvider）
  2. 在 Settings.LLM_PROVIDER 的 Literal 加入新值
  3. 在下方 get_llm_provider() 新增對應的 if 分支即可
"""
from __future__ import annotations

from app.config import settings
from .base import BaseLLMProvider
from .aoai_provider import AzureOpenAIProvider


def get_llm_provider() -> BaseLLMProvider:
    provider = settings.LLM_PROVIDER.lower()

    if provider == "azure_openai":
        return AzureOpenAIProvider(
            endpoint=settings.AOAI_ENDPOINT,
            api_key=settings.AOAI_API_KEY,
            deployment=settings.AOAI_DEPLOYMENT,
            api_version=settings.AOAI_API_VERSION,
        )

    # ── 未來擴充點 ────────────────────────────────────────────────────────────
    # if provider == "openai":
    #     from .openai_provider import OpenAIProvider
    #     return OpenAIProvider(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_MODEL)
    #
    # if provider == "anthropic":
    #     from .anthropic_provider import AnthropicProvider
    #     return AnthropicProvider(...)

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        "Check LLM_PROVIDER in .env and update factory.py."
    )
