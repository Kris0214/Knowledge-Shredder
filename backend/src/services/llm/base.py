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
    @abstractmethod
    async def shred_document(
        self, raw_text: str, domains: List[str]
    ) -> ShredderOutput:
        ...
