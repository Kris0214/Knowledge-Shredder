"""Abstract base class for all LLM providers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel, Field


class MicroModuleOutput(BaseModel):
    title: str
    content: str
    quiz_question: str
    quiz_options: List[str] = Field(..., min_length=4, max_length=4)
    quiz_answer: str                  # "A" | "B" | "C" | "D"
    reading_time_minutes: float


class ShredderOutput(BaseModel):
    modules: List[MicroModuleOutput]


class BaseLLMProvider(ABC):
    """
    每個 LLM 供應商只需實作這一個方法。
    切換供應商只需在 factory.py 新增對應的 class 並在 settings 修改 LLM_PROVIDER。
    """

    @abstractmethod
    async def shred_document(
        self, raw_text: str, domains: List[str]
    ) -> ShredderOutput:
        """將原始文字切割成微模組並附帶測驗題。"""
        ...
