"""Pydantic request / response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Domain
# ─────────────────────────────────────────────────────────────────────────────
class DomainCreate(BaseModel):
    domain_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class DomainResponse(BaseModel):
    domain_id: int
    domain_name: str
    description: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Document
# ─────────────────────────────────────────────────────────────────────────────
class DocumentUploadResponse(BaseModel):
    doc_id: int
    file_name: str
    status: str
    domain_ids: List[int]
    upload_timestamp: datetime


class DocumentListResponse(BaseModel):
    """列表用（不含 raw_text，避免回應過大）"""
    doc_id: int
    trainer_id: str
    file_name: str
    status: str
    upload_timestamp: datetime
    error_message: Optional[str]

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    doc_id: int
    trainer_id: str
    file_name: str
    status: str
    raw_text: Optional[str]
    upload_timestamp: datetime
    error_message: Optional[str]

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# MicroModule
# ─────────────────────────────────────────────────────────────────────────────
class MicroModuleResponse(BaseModel):
    module_id: int
    doc_id: int
    module_title: str
    module_content: str
    quiz_question: Optional[str]
    quiz_options: Optional[List[str]]
    quiz_answer: Optional[str]
    reading_time_minutes: float

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# Learning
# ─────────────────────────────────────────────────────────────────────────────
class QuizSubmission(BaseModel):
    answer: str = Field(..., description="選擇的答案代號，例如 'A'")
    time_taken_seconds: Optional[int] = None


class QuizResult(BaseModel):
    correct: bool
    correct_answer: str
    next_review_days: int


class UserProgressResponse(BaseModel):
    user_id: str
    total_modules_seen: int
    modules_due_today: int
    average_score: float
    domain_breakdown: dict


class DailyStatPoint(BaseModel):
    date: str          # "2026-04-16"
    total: int
    correct: int


class DomainAccuracy(BaseModel):
    domain_name: str
    total: int
    correct: int
    accuracy: float    # 0.0 ~ 1.0


class LearningStatsResponse(BaseModel):
    streak_days: int                        # 連續學習天數
    daily_trend: List[DailyStatPoint]       # 過去 14 天每日答題
    domain_accuracy: List[DomainAccuracy]   # 各領域正確率
    hardest_modules: List[dict]             # 最常答錯的模組 Top 5
