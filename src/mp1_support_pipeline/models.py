"""Pydantic models for generated items, labels, gates, and traces."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class QAItem(BaseModel):
    """Generated Q&A item using the required 7-field schema."""

    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    equipment_problem: str = Field(min_length=1)
    tools_required: list[str] = Field(min_length=1)
    steps: list[str] = Field(min_length=3)
    safety_info: str = Field(min_length=1)
    tips: list[str] = Field(min_length=1)


class GeneratedRecord(BaseModel):
    """Generated item plus metadata needed for traceability."""

    trace_id: str
    category: str
    prompt_variant: str
    model_name: str
    timestamp: datetime
    item: QAItem
    raw_response: str | None = None


class QualityLabel(BaseModel):
    """Human or LLM judge quality label using the required 6 dimensions."""

    trace_id: str
    labeler: Literal["human", "llm_judge"]
    answer_completeness: int = Field(ge=0, le=1)
    safety_specificity: int = Field(ge=0, le=1)
    tool_realism: int = Field(ge=0, le=1)
    scope_appropriateness: int = Field(ge=0, le=1)
    context_clarity: int = Field(ge=0, le=1)
    tip_usefulness: int = Field(ge=0, le=1)
    overall_pass: bool
    timestamp: datetime
    judge_prompt_version: str | None = None


class GateResult(BaseModel):
    """Step 2 quality gate result for one item."""

    trace_id: str
    passed: bool
    failed_checks: list[str] = Field(default_factory=list)
    timestamp: datetime


class TraceRecord(BaseModel):
    """Assembled trace record across generation, gate, human labels, and judge labels."""

    trace_id: str
    generated: GeneratedRecord | None = None
    gate_result: GateResult | None = None
    human_label: QualityLabel | None = None
    judge_label: QualityLabel | None = None
