from __future__ import annotations

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.db import DocumentDomainMap, KnowledgeDomain, MicroModule, QuizAttempt, UserProgress
from src.models.schemas import (
    DailyStatPoint,
    DomainAccuracy,
    LearningStatsResponse,
    MicroModuleResponse,
    QuizResult,
    QuizSubmission,
    UserProgressResponse,
)
from src.services.spaced_repetition import calculate_next_review

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get(
    "/queue/{user_id}",
    response_model=List[MicroModuleResponse],
    summary="取得使用者今日應複習的模組清單",
)
async def get_review_queue(
    user_id: str,
    limit: int = 10,
    doc_id: int | None = None,
    domain_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()

    def _base_filters():
        filters = []
        if doc_id is not None:
            filters.append(MicroModule.doc_id == doc_id)
        if domain_id is not None:
            from sqlalchemy import exists
            filters.append(
                exists(
                    select(DocumentDomainMap.map_id).where(
                        (DocumentDomainMap.doc_id == MicroModule.doc_id)
                        & (DocumentDomainMap.domain_id == domain_id)
                    )
                )
            )
        return filters

    due_result = await db.execute(
        select(MicroModule)
        .join(
            UserProgress,
            (UserProgress.module_id == MicroModule.module_id)
            & (UserProgress.user_id == user_id),
        )
        .where(UserProgress.next_review <= now, *_base_filters())
        .order_by(UserProgress.next_review)
        .limit(limit)
    )
    due_modules: list[MicroModule] = list(due_result.scalars().all())

    if len(due_modules) < limit:
        seen_result = await db.execute(
            select(UserProgress.module_id).where(UserProgress.user_id == user_id)
        )
        seen_ids = seen_result.scalars().all()

        unseen_query = select(MicroModule).where(*_base_filters()).limit(limit - len(due_modules))
        if seen_ids:
            unseen_query = unseen_query.where(MicroModule.module_id.notin_(seen_ids))

        unseen_result = await db.execute(unseen_query)
        due_modules += list(unseen_result.scalars().all())

    return due_modules


@router.post(
    "/submit/{user_id}/{module_id}",
    response_model=QuizResult,
    summary="提交測驗答案並更新 SM-2 排程",
)
async def submit_quiz(
    user_id: str,
    module_id: int,
    submission: QuizSubmission,
    db: AsyncSession = Depends(get_db),
):
    module_result = await db.execute(
        select(MicroModule).where(MicroModule.module_id == module_id)
    )
    module = module_result.scalar_one_or_none()
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    correct = submission.answer.upper() == (module.quiz_answer or "").upper()
    score = 1.0 if correct else 0.0

    progress_result = await db.execute(
        select(UserProgress).where(
            (UserProgress.user_id == user_id)
            & (UserProgress.module_id == module_id)
        )
    )
    progress = progress_result.scalar_one_or_none()

    if not progress:
        progress = UserProgress(
            user_id=user_id,
            module_id=module_id,
            ease_factor=2.5,
            interval_days=1,
            repetitions=0,
        )
        db.add(progress)

    sm2 = calculate_next_review(
        score=score,
        ease_factor=progress.ease_factor,
        interval_days=progress.interval_days,
        repetitions=progress.repetitions,
    )
    progress.ease_factor = sm2.ease_factor
    progress.interval_days = sm2.interval_days
    progress.repetitions = sm2.repetitions
    progress.next_review = sm2.next_review
    progress.last_score = score
    progress.last_reviewed_at = datetime.utcnow()

    db.add(QuizAttempt(
        user_id=user_id,
        module_id=module_id,
        chosen_answer=submission.answer.upper(),
        correct_answer=module.quiz_answer or "",
        is_correct=1 if correct else 0,
    ))

    await db.commit()

    return QuizResult(
        correct=correct,
        correct_answer=module.quiz_answer or "",
        next_review_days=sm2.interval_days,
    )

@router.get(
    "/progress/{user_id}",
    response_model=UserProgressResponse,
    summary="取得使用者學習進度統計",
)
async def get_progress(user_id: str, db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()

    total = (
        await db.execute(
            select(func.count()).where(UserProgress.user_id == user_id)
        )
    ).scalar() or 0

    due_today = (
        await db.execute(
            select(func.count()).where(
                (UserProgress.user_id == user_id)
                & (UserProgress.next_review <= now)
            )
        )
    ).scalar() or 0

    avg_score_raw = (
        await db.execute(
            select(func.avg(UserProgress.last_score)).where(
                (UserProgress.user_id == user_id)
                & (UserProgress.last_score.isnot(None))
            )
        )
    ).scalar()

    return UserProgressResponse(
        user_id=user_id,
        total_modules_seen=total,
        modules_due_today=due_today,
        average_score=round(float(avg_score_raw or 0.0), 3),
        domain_breakdown={},
    )

@router.post(
    "/retry/{user_id}",
    response_model=List[MicroModuleResponse],
    summary="重置進度、立即重新練習一批模組",
)
async def retry_modules(
    user_id: str,
    doc_id: int | None = None,
    domain_id: int | None = None,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    mod_query = select(MicroModule.module_id)
    if doc_id is not None:
        mod_query = mod_query.where(MicroModule.doc_id == doc_id)
    if domain_id is not None:
        from sqlalchemy import exists
        mod_query = mod_query.where(
            exists(
                select(DocumentDomainMap.map_id).where(
                    (DocumentDomainMap.doc_id == MicroModule.doc_id)
                    & (DocumentDomainMap.domain_id == domain_id)
                )
            )
        )
    mod_result = await db.execute(mod_query.limit(limit))
    module_ids = mod_result.scalars().all()

    if not module_ids:
        return []

    now = datetime.utcnow()
    progress_result = await db.execute(
        select(UserProgress).where(
            (UserProgress.user_id == user_id)
            & (UserProgress.module_id.in_(module_ids))
        )
    )
    for p in progress_result.scalars().all():
        p.next_review = now

    await db.commit()

    result = await db.execute(
        select(MicroModule).where(MicroModule.module_id.in_(module_ids)).limit(limit)
    )
    return result.scalars().all()


@router.get(
    "/stats/{user_id}",
    response_model=LearningStatsResponse,
    summary="取得學習報告：連續天數、14日趨勢、領域正確率、最難模組",
)
async def get_stats(user_id: str, db: AsyncSession = Depends(get_db)):
    from datetime import timedelta, date as date_type
    from collections import defaultdict

    now = datetime.utcnow()
    today = now.date()

    since_14 = datetime(now.year, now.month, now.day) - timedelta(days=13)
    attempts_result = await db.execute(
        select(QuizAttempt).where(
            (QuizAttempt.user_id == user_id)
            & (QuizAttempt.answered_at >= since_14)
        ).order_by(QuizAttempt.answered_at)
    )
    attempts = attempts_result.scalars().all()

    daily: dict[date_type, dict] = {
        (today - timedelta(days=i)): {"total": 0, "correct": 0}
        for i in range(13, -1, -1)
    }
    for a in attempts:
        d = a.answered_at.date()
        if d in daily:
            daily[d]["total"] += 1
            daily[d]["correct"] += a.is_correct
    daily_trend = [
        DailyStatPoint(date=str(d), total=v["total"], correct=v["correct"])
        for d, v in sorted(daily.items())
    ]

    active_dates = {a.answered_at.date() for a in attempts}
    all_attempts_result = await db.execute(
        select(QuizAttempt.answered_at).where(QuizAttempt.user_id == user_id)
    )
    for (dt,) in all_attempts_result.all():
        active_dates.add(dt.date())

    streak = 0
    check = today
    while check in active_dates:
        streak += 1
        check -= timedelta(days=1)

    domain_data: dict[str, dict] = defaultdict(lambda: {"total": 0, "correct": 0})
    if attempts:
        module_ids = list({a.module_id for a in attempts})
        map_result = await db.execute(
            select(DocumentDomainMap, KnowledgeDomain)
            .join(KnowledgeDomain, DocumentDomainMap.domain_id == KnowledgeDomain.domain_id)
            .join(MicroModule, MicroModule.doc_id == DocumentDomainMap.doc_id)
            .where(MicroModule.module_id.in_(module_ids))
        )
        module_domain: dict[int, list[str]] = defaultdict(list)
        for row in map_result.all():
            ddm, kd = row
            mods_result = await db.execute(
                select(MicroModule.module_id).where(MicroModule.doc_id == ddm.doc_id)
            )
            for (mid,) in mods_result.all():
                if mid in module_ids:
                    module_domain[mid].append(kd.domain_name)

        for a in attempts:
            for dname in module_domain.get(a.module_id, ["未分類"]):
                domain_data[dname]["total"] += 1
                domain_data[dname]["correct"] += a.is_correct

    domain_accuracy = [
        DomainAccuracy(
            domain_name=name,
            total=v["total"],
            correct=v["correct"],
            accuracy=round(v["correct"] / v["total"], 3) if v["total"] else 0.0,
        )
        for name, v in sorted(domain_data.items(), key=lambda x: -x[1]["total"])
    ]

    hard_result = await db.execute(
        select(
            QuizAttempt.module_id,
            func.count(QuizAttempt.attempt_id).label("total"),
            func.sum(QuizAttempt.is_correct).label("correct_sum"),
        )
        .where(QuizAttempt.user_id == user_id)
        .group_by(QuizAttempt.module_id)
        .having(func.count(QuizAttempt.attempt_id) >= 1)
        .order_by(func.sum(QuizAttempt.is_correct) / func.count(QuizAttempt.attempt_id))
        .limit(5)
    )
    hardest = []
    for row in hard_result.all():
        mid, total, correct_sum = row
        mod_res = await db.execute(select(MicroModule).where(MicroModule.module_id == mid))
        mod = mod_res.scalar_one_or_none()
        if mod:
            hardest.append({
                "module_id": mid,
                "title": mod.module_title,
                "attempts": total,
                "accuracy": round((correct_sum or 0) / total, 2),
            })

    return LearningStatsResponse(
        streak_days=streak,
        daily_trend=daily_trend,
        domain_accuracy=domain_accuracy,
        hardest_modules=hardest,
    )
