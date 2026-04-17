"""微模組查詢。"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import DocumentDomainMap, MicroModule, SourceDocument
from app.models.schemas import MicroModuleResponse

router = APIRouter(prefix="/modules", tags=["modules"])


@router.get("", response_model=List[MicroModuleResponse])
async def list_modules(
    domain_id: Optional[int] = Query(None, description="依領域篩選"),
    doc_id: Optional[int] = Query(None, description="依文件篩選"),
    db: AsyncSession = Depends(get_db),
):
    query = select(MicroModule)

    if domain_id is not None:
        query = (
            query.join(SourceDocument, MicroModule.doc_id == SourceDocument.doc_id)
            .join(DocumentDomainMap, DocumentDomainMap.doc_id == SourceDocument.doc_id)
            .where(DocumentDomainMap.domain_id == domain_id)
        )

    if doc_id is not None:
        query = query.where(MicroModule.doc_id == doc_id)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{module_id}", response_model=MicroModuleResponse)
async def get_module(module_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MicroModule).where(MicroModule.module_id == module_id)
    )
    module = result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return module
