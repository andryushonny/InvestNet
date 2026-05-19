from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Person(SQLModel, table=True):
    __tablename__ = "person"
    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str
    primary_email: Optional[str] = Field(default=None, unique=True, index=True)
    emails: Optional[str] = None  # JSON list
    linkedin_url: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None  # 'gmail' | 'linkedin' | 'manual' | 'merged'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Interaction(SQLModel, table=True):
    __tablename__ = "interaction"
    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    channel: str  # 'email' | 'linkedin_msg' | 'meeting' | 'manual'
    direction: str  # 'incoming' | 'outgoing'
    occurred_at: datetime
    subject: Optional[str] = None
    body_cleaned: Optional[str] = None
    body_hash: str = Field(unique=True, index=True)
    raw_message_id: Optional[str] = None
    extra: Optional[str] = None  # JSON


class InvestmentProfile(SQLModel, table=True):
    __tablename__ = "investment_profile"
    person_id: int = Field(primary_key=True, foreign_key="person.id")
    investment_interests: Optional[str] = None  # JSON
    preferred_ticket: Optional[str] = None
    geography: Optional[str] = None  # JSON
    stage_focus: Optional[str] = None  # JSON
    keywords: Optional[str] = None  # JSON
    ai_summary: Optional[str] = None
    confidence: Optional[float] = None
    sources: Optional[str] = None  # JSON
    enriched_at: Optional[datetime] = None
    raw_enrichment_data: Optional[str] = None  # JSON


class InvestmentCase(SQLModel, table=True):
    __tablename__ = "investment_case"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str
    stage: Optional[str] = None
    geography: Optional[str] = None
    sector: Optional[str] = None
    ticket_range: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    embedding_id: Optional[int] = None


class Deal(SQLModel, table=True):
    __tablename__ = "deal"
    id: Optional[int] = Field(default=None, primary_key=True)
    person_id: int = Field(foreign_key="person.id", index=True)
    case_id: int = Field(foreign_key="investment_case.id", index=True)
    status: str = "new"
    score: Optional[float] = None
    reasoning: Optional[str] = None  # JSON
    next_action: Optional[str] = None
    next_action_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GeneratedEmailDraft(SQLModel, table=True):
    __tablename__ = "generated_email_draft"
    id: Optional[int] = Field(default=None, primary_key=True)
    deal_id: int = Field(foreign_key="deal.id", index=True)
    subject: str
    body: str
    model_used: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    user_edited: int = 0
    user_sent: int = 0


class BackgroundTask(SQLModel, table=True):
    __tablename__ = "background_task"
    id: Optional[int] = Field(default=None, primary_key=True)
    kind: str
    status: str = "queued"  # 'queued' | 'running' | 'done' | 'failed'
    progress: float = 0.0
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
