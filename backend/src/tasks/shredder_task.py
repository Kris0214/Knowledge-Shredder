"""
Celery 非同步任務：Knowledge Shredder
======================================
將 LLM 呼叫移到 worker，避免 API 請求 timeout。
Worker 從 DB 讀取文件 → 安全過濾 → 呼叫 LLM → 寫回微模組。
"""
from __future__ import annotations

import asyncio

from celery import Celery
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings
from app.models.db import (
    DocumentDomainMap,
    KnowledgeDomain,
    MicroModule,
    SourceDocument,
)
from app.services.content_filter import check_prompt_injection, sanitize_for_prompt
from app.services.llm.factory import get_llm_provider

# ── Celery App ────────────────────────────────────────────────────────────────
celery_app = Celery(
    "kgi_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]

# ── 同步 DB 引擎（Celery worker 不用 async）────────────────────────────────────
_sync_url = (
    settings.DATABASE_URL
    .replace("+aiosqlite", "")
    .replace("+asyncpg", "")
)
_sync_engine = create_engine(_sync_url, pool_pre_ping=True)
_SyncSession = sessionmaker(_sync_engine, expire_on_commit=False)


# ── Task ──────────────────────────────────────────────────────────────────────
@celery_app.task(
    bind=True,
    name="tasks.shred_document",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def shred_document_task(self, doc_id: int) -> dict:
    """
    1. 從 DB 取得文件與領域標籤
    2. Prompt Injection 安全檢查
    3. 呼叫 LLM 產生微模組
    4. 將結果寫回 DB，更新文件狀態
    """
    with _SyncSession() as session:
        doc: SourceDocument | None = session.get(SourceDocument, doc_id)
        if not doc:
            return {"error": f"Document {doc_id} not found"}

        try:
            # ① 更新狀態為 processing
            doc.status = "processing"
            session.commit()

            # ② 取得領域名稱
            domain_names = _get_domain_names(session, doc_id)

            # ③ 安全過濾
            is_safe, reason = check_prompt_injection(doc.raw_text or "")
            if not is_safe:
                _fail(session, doc, f"Content rejected: {reason}")
                return {"error": doc.error_message}

            clean_text = sanitize_for_prompt(doc.raw_text or "")

            # ④ 呼叫 LLM（async 在 sync context 執行）
            provider = get_llm_provider()
            result = asyncio.run(
                provider.shred_document(clean_text, domain_names)
            )

            # ⑤ 寫入微模組
            for m in result.modules:
                session.add(
                    MicroModule(
                        doc_id=doc_id,
                        module_title=m.title,
                        module_content=m.content,
                        quiz_question=m.quiz_question,
                        quiz_options=m.quiz_options,
                        quiz_answer=m.quiz_answer,
                        reading_time_minutes=m.reading_time_minutes,
                    )
                )

            doc.status = "done"
            session.commit()
            return {"status": "done", "modules_created": len(result.modules)}

        except Exception as exc:
            _fail(session, doc, str(exc))
            raise self.retry(exc=exc)


# ── Helpers ───────────────────────────────────────────────────────────────────
def _get_domain_names(session: Session, doc_id: int) -> list[str]:
    rows = session.execute(
        select(KnowledgeDomain.domain_name)
        .join(DocumentDomainMap, DocumentDomainMap.domain_id == KnowledgeDomain.domain_id)
        .where(DocumentDomainMap.doc_id == doc_id)
    ).scalars().all()
    return list(rows)


def _fail(session: Session, doc: SourceDocument, message: str) -> None:
    doc.status = "failed"
    doc.error_message = message
    session.commit()
