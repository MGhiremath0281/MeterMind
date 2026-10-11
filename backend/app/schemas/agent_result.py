from decimal import Decimal
from enum import Enum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AgentStatus(str, Enum):
    COMPLETED = "completed"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    FAILED = "failed"


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class FindingStatus(str, Enum):
    CONFIRMED = "confirmed"
    SUSPECTED = "suspected"
    UNRESOLVED = "unresolved"


class EvidenceReference(BaseModel):
    """Points to evidence produced by a deterministic tool or trusted source."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    evidence_id: str = Field(min_length=1, max_length=200)
    source: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)


class AgentFinding(BaseModel):
    """A single billing-related finding from an investigating agent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    finding_id: str = Field(min_length=1, max_length=200)
    category: str = Field(
        description=(
            "For example: duplicate_event, missing_event, pricing_mismatch, "
            "invoice_discrepancy, or evidence_gap."
        ),
        min_length=1,
        max_length=100,
    )
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1, max_length=3000)
    status: FindingStatus
    severity: FindingSeverity
    evidence: list[EvidenceReference] = Field(default_factory=list)
    affected_customer_id: str | None = Field(default=None, max_length=200)
    affected_event_ids: list[str] = Field(default_factory=list)
    affected_invoice_line_ids: list[str] = Field(default_factory=list)
    financial_impact: Decimal | None = None
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    limitations: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def validate_evidence_and_impact(self) -> Self:
        if self.status == FindingStatus.CONFIRMED and not self.evidence:
            raise ValueError(
                "A confirmed finding must include at least one evidence reference."
            )

        if self.financial_impact is not None:
            if not self.financial_impact.is_finite():
                raise ValueError("Financial impact must be a finite decimal.")

            if self.currency is None:
                raise ValueError(
                    "Currency is required when financial impact is provided."
                )

        return self


class AgentResult(BaseModel):
    """Validated output contract shared by all MeterMind investigation agents."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    agent_name: str = Field(min_length=1, max_length=100)
    case_id: str = Field(min_length=1, max_length=200)
    status: AgentStatus
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[AgentFinding] = Field(default_factory=list)
    evidence_reviewed: list[EvidenceReference] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_result_status(self) -> Self:
        if self.status == AgentStatus.FAILED and self.findings:
            raise ValueError("A failed agent result must not report findings.")

        if (
            self.status == AgentStatus.NEEDS_MORE_EVIDENCE
            and not self.limitations
            and not self.recommended_next_steps
        ):
            raise ValueError(
                "An agent requesting more evidence must explain the gap "
                "or recommend a next step."
            )

        return self