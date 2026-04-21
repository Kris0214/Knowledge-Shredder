from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.db import KnowledgeDomain
from src.models.schemas import DomainCreate, DomainResponse

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("", response_model=List[DomainResponse])
async def list_domains(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KnowledgeDomain).order_by(KnowledgeDomain.domain_name)
    )
    return result.scalars().all()


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(payload: DomainCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(KnowledgeDomain).where(KnowledgeDomain.domain_name == payload.domain_name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="領域名稱已存在")

    domain = KnowledgeDomain(**payload.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain


@router.put("/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: int, payload: DomainCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(KnowledgeDomain).where(KnowledgeDomain.domain_id == domain_id)
    )
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    domain.domain_name = payload.domain_name
    domain.description = payload.description
    await db.commit()
    await db.refresh(domain)
    return domain


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(domain_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(KnowledgeDomain).where(KnowledgeDomain.domain_id == domain_id)
    )
    domain = result.scalar_one_or_none()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    await db.delete(domain)
    await db.commit()
