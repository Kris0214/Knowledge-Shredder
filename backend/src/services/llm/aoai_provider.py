"""Azure OpenAI 實作 — 透過 openai SDK 呼叫 AOAI。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List

import openai

from .base import BaseLLMProvider, ShredderOutput

# Prompt 文字從外部 .txt 讀取，換 LLM 只需修改 prompts/ 目錄下的文字檔
_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()


def _build_prompt(raw_text: str, domains: List[str]) -> str:
    domains_str = "、".join(f"【{d}】" for d in domains)
    template = _load_prompt("user.txt")
    return template.format(domains=domains_str, raw_text=raw_text)


class AzureOpenAIProvider(BaseLLMProvider):
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str,
    ) -> None:
        self._client = openai.AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
        self._deployment = deployment

    async def shred_document(
        self, raw_text: str, domains: List[str]
    ) -> ShredderOutput:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=[
                {"role": "system", "content": _load_prompt("system.txt")},
                {"role": "user", "content": _build_prompt(raw_text, domains)},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=4096,
        )
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return ShredderOutput(**data)
