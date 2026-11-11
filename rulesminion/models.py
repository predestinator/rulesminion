"""Structured brief and change-report models returned by RulesMinion."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("text", "value", "amount", "label", "name", "description"):
            if value.get(key):
                return str(value[key]).strip()
        return " ".join(str(v) for v in value.values() if v)
    return str(value).strip()


class PrizeItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    place: str = ""
    amount: str = ""
    notes: str = ""

    @field_validator("place", "amount", "notes", mode="before")
    @classmethod
    def _as_str(cls, value: Any) -> str:
        return _stringify(value)


class DeadlineItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = "deadline"
    as_stated: str = ""
    timezone_as_stated: str = ""
    ist: str = ""
    confidence: str = "medium"

    @field_validator(
        "label", "as_stated", "timezone_as_stated", "ist", "confidence", mode="before"
    )
    @classmethod
    def _as_str(cls, value: Any) -> str:
        return _stringify(value)


class HackathonBrief(BaseModel):
    """Fields the OpenMinion agent must fill from a hackathon page."""

    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    organizer: str = ""
    format: str = ""
    prize_pool: str = ""
    prizes: list[PrizeItem] = Field(default_factory=list)
    deadlines: list[DeadlineItem] = Field(default_factory=list)
    india_eligible: str = "unclear"
    eligibility_summary: str = ""
    eligibility_evidence: str = ""
    submission_checklist: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("format", mode="before")
    @classmethod
    def _normalize_format(cls, value: Any) -> str:
        text = _stringify(value).lower()
        if not text:
            return ""
        if "hybrid" in text:
            return "hybrid"
        if "virtual" in text or "online" in text:
            return "online"
        if "in-person" in text or "in person" in text or "offline" in text:
            return "in-person"
        return text

    @field_validator("india_eligible", mode="before")
    @classmethod
    def _normalize_india(cls, value: Any) -> str:
        text = _stringify(value).lower()
        if text in {"yes", "y", "true", "eligible"}:
            return "yes"
        if text in {"no", "n", "false", "ineligible"}:
            return "no"
        return "unclear"

    @field_validator("prizes", mode="before")
    @classmethod
    def _coerce_prizes(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"place": "", "amount": value, "notes": ""}]
        if isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    out.append({"place": "", "amount": item, "notes": ""})
                else:
                    out.append(item)
            return out
        return value

    @field_validator("deadlines", mode="before")
    @classmethod
    def _coerce_deadlines(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, str):
            return [{"label": "deadline", "as_stated": value}]
        if isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    out.append({"label": "deadline", "as_stated": item})
                else:
                    out.append(item)
            return out
        return value

    @field_validator("submission_checklist", "notes", mode="before")
    @classmethod
    def _coerce_str_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value.strip() else []
        if isinstance(value, list):
            return [_stringify(item) for item in value if _stringify(item)]
        return [_stringify(value)]


class ChangeItem(BaseModel):
    path: str
    before: str | None = None
    after: str | None = None


class ChangeReport(BaseModel):
    status: str
    previous_checked_at_ist: str | None = None
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    changed: list[ChangeItem] = Field(default_factory=list)
    summary: str = ""


class CheckResult(BaseModel):
    brief: HackathonBrief
    changes: ChangeReport
    snapshot_id: str
    checked_at_ist: str
    extractor: str = "openminion"
    session_id: str = ""
    elapsed_ms: int | None = None
    page_title: str = ""
    warnings: list[str] = Field(default_factory=list)
