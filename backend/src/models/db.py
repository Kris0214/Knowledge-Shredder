"""SQLAlchemy ORM models — one file per table group."""
import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    DateTime,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# 領域字典
# ─────────────────────────────────────────────────────────────────────────────
class KnowledgeDomain(Base):
    __tablename__ = "knowledge_domains"

    domain_id = Column(Integer, primary_key=True, autoincrement=True)
    domain_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    mappings = relationship(
        "DocumentDomainMap", back_populates="domain", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 上傳的原始文件
# ─────────────────────────────────────────────────────────────────────────────
class SourceDocument(Base):
    __tablename__ = "source_documents"

    doc_id = Column(Integer, primary_key=True, autoincrement=True)
    trainer_id = Column(String(100), nullable=False)
    file_name = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=True)
    upload_timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    # pending → processing → done | failed
    status = Column(String(20), default="pending", nullable=False)
    error_message = Column(Text, nullable=True)

    mappings = relationship(
        "DocumentDomainMap", back_populates="document", cascade="all, delete-orphan"
    )
    modules = relationship(
        "MicroModule", back_populates="document", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 多對多中介表
# ─────────────────────────────────────────────────────────────────────────────
class DocumentDomainMap(Base):
    __tablename__ = "document_domain_map"

    map_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(
        Integer,
        ForeignKey("source_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    domain_id = Column(
        Integer,
        ForeignKey("knowledge_domains.domain_id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (UniqueConstraint("doc_id", "domain_id", name="uq_doc_domain"),)

    document = relationship("SourceDocument", back_populates="mappings")
    domain = relationship("KnowledgeDomain", back_populates="mappings")


# ─────────────────────────────────────────────────────────────────────────────
# AI 生成的微模組
# ─────────────────────────────────────────────────────────────────────────────
class MicroModule(Base):
    __tablename__ = "micro_modules"

    module_id = Column(Integer, primary_key=True, autoincrement=True)
    doc_id = Column(
        Integer,
        ForeignKey("source_documents.doc_id", ondelete="CASCADE"),
        nullable=False,
    )
    module_title = Column(String(200), nullable=False)
    module_content = Column(Text, nullable=False)
    quiz_question = Column(Text, nullable=True)
    # ["A) ...", "B) ...", "C) ...", "D) ..."]
    quiz_options = Column(JSON, nullable=True)
    quiz_answer = Column(String(10), nullable=True)   # "A" | "B" | "C" | "D"
    reading_time_minutes = Column(Float, default=2.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    document = relationship("SourceDocument", back_populates="modules")
    progress_records = relationship(
        "UserProgress", back_populates="module", cascade="all, delete-orphan"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 學習者進度（SM-2 間隔重複）
# ─────────────────────────────────────────────────────────────────────────────
class UserProgress(Base):
    __tablename__ = "user_progress"

    progress_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    module_id = Column(
        Integer,
        ForeignKey("micro_modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    ease_factor = Column(Float, default=2.5)        # SM-2 EF，初始 2.5
    interval_days = Column(Integer, default=1)      # 下次複習間隔天數
    next_review = Column(DateTime, nullable=True)   # 下次應複習時間
    repetitions = Column(Integer, default=0)        # 連續答對次數
    last_score = Column(Float, nullable=True)       # 0.0 ~ 1.0
    last_reviewed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "module_id", name="uq_user_module"),
    )

    module = relationship("MicroModule", back_populates="progress_records")


# ─────────────────────────────────────────────────────────────────────────────
# 答題歷史（每次作答一筆，用於趨勢分析）
# ─────────────────────────────────────────────────────────────────────────────
class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    attempt_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True)
    module_id = Column(
        Integer,
        ForeignKey("micro_modules.module_id", ondelete="CASCADE"),
        nullable=False,
    )
    answered_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    chosen_answer = Column(String(10), nullable=False)
    correct_answer = Column(String(10), nullable=False)
    is_correct = Column(Integer, nullable=False)  # 1 = 答對, 0 = 答錯

    module = relationship("MicroModule")
