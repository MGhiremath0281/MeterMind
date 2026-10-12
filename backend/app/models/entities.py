from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class Customer(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(100), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ReconciliationCase(Base):
    __tablename__ = "reconciliation_cases"

    case_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    findings: Mapped[list["AgentFinding"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )


class AgentFinding(Base):
    __tablename__ = "agent_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(
        ForeignKey("reconciliation_cases.case_id"), nullable=False, index=True
    )
    finding_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    case: Mapped[ReconciliationCase] = relationship(back_populates="findings")


class InvestigationRun(Base):
    __tablename__ = "investigation_runs"

    case_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    audit_status: Mapped[str] = mapped_column(String(50), nullable=False)
    supervisor_decision: Mapped[str] = mapped_column(
        String(50), nullable=False
    )
    supervisor_reason: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    case_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    investigation_cases: Mapped[list["InvestigationCase"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
    )


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("investigation_runs.case_id"),
        nullable=False,
        index=True,
    )
    group_key: Mapped[str] = mapped_column(String(200), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    finding_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    categories_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    finding_ids_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    invoice_line_ids_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    findings_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    evidence_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    requires_review: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    run: Mapped["InvestigationRun"] = relationship(
        back_populates="investigation_cases"
    )
