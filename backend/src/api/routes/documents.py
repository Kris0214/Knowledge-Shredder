"""文件上傳與查詢。"""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings  # noqa: F401 – UPLOAD_MAX_SIZE_MB
from app.database import get_db
from app.models.db import DocumentDomainMap, KnowledgeDomain, MicroModule, SourceDocument
from app.models.schemas import DocumentResponse, DocumentListResponse, DocumentUploadResponse
from app.services.content_filter import check_prompt_injection, sanitize_for_prompt
from app.services.document_parser import extract_text
from app.services.llm.factory import get_llm_provider

router = APIRouter(prefix="/documents", tags=["documents"])

_MAX_BYTES = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="上傳訓練文件並觸發 AI 切割",
)
async def upload_document(
    file: UploadFile = File(...),
    trainer_id: str = Form(...),
    domain_ids: str = Form(
        ..., description="JSON 陣列格式的領域 ID，例如 [1,2,3]（至少一個）"
    ),
    db: AsyncSession = Depends(get_db),
):
    # ① 檔案大小限制
    content = await file.read()
    if len(content) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"檔案超過 {settings.UPLOAD_MAX_SIZE_MB} MB 限制",
        )

    # ② 解析 domain_ids
    try:
        ids: List[int] = json.loads(domain_ids)
        if not ids or not all(isinstance(i, int) for i in ids):
            raise ValueError
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail="domain_ids 必須是非空的整數 JSON 陣列，例如 [1,2]",
        )

    # ③ 確認所有領域存在
    result = await db.execute(
        select(KnowledgeDomain).where(KnowledgeDomain.domain_id.in_(ids))
    )
    found = result.scalars().all()
    if len(found) != len(set(ids)):
        raise HTTPException(status_code=404, detail="部分 domain_id 不存在")

    # ④ 擷取文字
    try:
        raw_text = extract_text(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc))

    # ⑤ 存入 DB
    doc = SourceDocument(
        trainer_id=trainer_id,
        file_name=file.filename or "upload",
        raw_text=raw_text,
        status="pending",
    )
    db.add(doc)
    await db.flush()

    for domain_id in set(ids):
        db.add(DocumentDomainMap(doc_id=doc.doc_id, domain_id=domain_id))

    await db.commit()
    await db.refresh(doc)

    # 先把 return 需要的值存起來，避免 _shred_sync 執行後 doc 物件狀態改變
    resp_doc_id = doc.doc_id
    resp_file_name = doc.file_name
    resp_upload_timestamp = doc.upload_timestamp
    domain_ids_list = list(set(ids))

    # ⑥ 呼叫 LLM 粉碎文件（同步，在 API 程序內執行）
    await _shred_sync(db, doc.doc_id, doc.raw_text or "", [d.domain_name for d in found])

    # 重新查詢最新狀態，不依賴可能 detached 的 doc 物件
    result2 = await db.execute(
        select(SourceDocument).where(SourceDocument.doc_id == resp_doc_id)
    )
    final_doc = result2.scalar_one_or_none()
    final_status = final_doc.status if final_doc else "pending"

    return DocumentUploadResponse(
        doc_id=resp_doc_id,
        file_name=resp_file_name,
        status=final_status,
        domain_ids=domain_ids_list,
        upload_timestamp=resp_upload_timestamp,
    )


async def _shred_sync(
    db: AsyncSession, doc_id: int, raw_text: str, domain_names: List[str]
) -> None:
    """在 API 程序內完成 AI 粉碎，將結果寫入資料庫。"""
    async def _set_status(status: str, error: str | None = None) -> None:
        try:
            res = await db.execute(
                select(SourceDocument).where(SourceDocument.doc_id == doc_id)
            )
            d = res.scalar_one_or_none()
            if d:
                d.status = status
                d.error_message = error
                await db.commit()
        except Exception:
            pass

    try:
        await _set_status("processing")

        is_safe, reason = check_prompt_injection(raw_text)
        if not is_safe:
            await _set_status("failed", f"Content rejected: {reason}")
            return

        clean_text = sanitize_for_prompt(raw_text)
        provider = get_llm_provider()
        result = await provider.shred_document(clean_text, domain_names)

        for m in result.modules:
            db.add(MicroModule(
                doc_id=doc_id,
                module_title=m.title,
                module_content=m.content,
                quiz_question=m.quiz_question,
                quiz_options=m.quiz_options,
                quiz_answer=m.quiz_answer,
                reading_time_minutes=m.reading_time_minutes,
            ))

        await db.commit()
        await _set_status("pending_review")

    except Exception as exc:
        try:
            await db.rollback()
        except Exception:
            pass
        await _set_status("failed", str(exc)[:500])


@router.get("", response_model=List[DocumentListResponse])
async def list_documents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SourceDocument).order_by(SourceDocument.upload_timestamp.desc())
    )
    return result.scalars().all()


@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """刪除文件及其所有模組、學習紀錄（CASCADE）。"""
    result = await db.execute(
        select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()


@router.post("/{doc_id}/confirm", response_model=DocumentListResponse)
async def confirm_document(doc_id: int, db: AsyncSession = Depends(get_db)):
    """將 pending_review 文件確認發布為 done。"""
    result = await db.execute(
        select(SourceDocument).where(SourceDocument.doc_id == doc_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != "pending_review":
        raise HTTPException(
            status_code=400,
            detail=f"文件狀態非 pending_review（目前：{doc.status}）",
        )
    doc.status = "done"
    await db.commit()
    await db.refresh(doc)
    return doc
