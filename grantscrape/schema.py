"""Data contracts: what the extractor (agent or API) writes per chunk, and the final Award row."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

RecipientType = Literal["person", "organisation", "group", "unknown"]


class RawRow(BaseModel):
    """One award as written by the extractor for a single chunk."""

    recipient_name: str
    recipient_raw: str | None = None
    recipient_type: RecipientType = "unknown"
    amount: float | None = None
    amount_raw: str | None = None
    currency: str | None = None
    year: int | None = None
    project_title: str | None = None
    project_description: str | None = None
    purpose: str | None = None
    discipline: str | None = None
    program: str | None = None
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str | None = None

    @field_validator("recipient_type", mode="before")
    @classmethod
    def _type_alias(cls, v):
        """Accept the production schema's values (individual / organization) as well as ours."""
        return {"individual": "person", "organization": "organisation", None: "unknown"}.get(v, v)

    @field_validator("recipient_name", "evidence")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("must not be empty")
        return v.strip()

    @field_validator("amount", mode="before")
    @classmethod
    def _amount_from_string(cls, v):
        if isinstance(v, str):
            from .normalize import parse_amount

            return parse_amount(v)[0]
        return v


class RawExtraction(BaseModel):
    """Contents of runs/<slug>/rows/<chunk_id>.json."""

    chunk_id: str
    rows: list[RawRow] = Field(default_factory=list)
    chunk_notes: str | None = None


class Award(BaseModel):
    """Final validated row. `to_export_row` in export.py is the single place that maps this to the output schema."""

    foundation: str
    foundation_url: str | None = None
    recipient_name: str
    recipient_raw: str | None = None
    recipient_type: RecipientType = "unknown"
    amount: float | None = None
    amount_raw: str | None = None
    currency: str | None = None
    year: int | None = None
    project_title: str | None = None
    project_description: str | None = None
    purpose: str | None = None
    discipline: str | None = None
    program: str | None = None
    source_url: str
    evidence: str
    confidence: float
    agent_confidence: float
    rule_score: float
    review_reasons: list[str] = Field(default_factory=list)
    notes: str | None = None
    chunk_id: str
    run_id: str
    reviewed: bool = False
