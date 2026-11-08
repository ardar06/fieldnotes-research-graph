from datetime import date, datetime
import re
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

Status = Literal["unreviewed", "corroborated", "disputed"]


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=180)
    purpose: str = Field(default="", max_length=500)


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    purpose: str
    created_at: datetime


class InitialRelationshipCreate(BaseModel):
    other_person_id: str
    source_id: str
    label: str = Field(min_length=1, max_length=240)
    details: str = Field(default="", max_length=5000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Status = "unreviewed"


class PersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    identity_id: str | None = None
    aliases: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=5000)
    initial_relationship: InitialRelationshipCreate | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class PersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    identity_id: str | None
    name: str
    aliases: list[str]
    notes: str
    created_at: datetime


class GlobalPersonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    canonical_name: str
    created_at: datetime


class UsernameHandlesCreate(BaseModel):
    usernames: list[str] = Field(min_length=1, max_length=10)

    @field_validator("usernames")
    @classmethod
    def validate_usernames(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", value) for value in cleaned):
            raise ValueError("Usernames must be 1-64 letters, numbers, dots, underscores, or hyphens; enter without @")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Duplicate usernames are not allowed")
        return cleaned


class UsernameHandleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    created_at: datetime


class UsernameSiteOut(BaseModel):
    name: str
    home_url: str


class UsernameSearchRequest(BaseModel):
    site_names: list[str] = Field(min_length=1, max_length=25)
    confirm_authorized: bool

    @field_validator("confirm_authorized")
    @classmethod
    def require_authorization_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Confirm that this search has a consent or public-interest basis")
        return value

    @field_validator("site_names")
    @classmethod
    def unique_site_names(cls, values: list[str]) -> list[str]:
        if len(set(values)) != len(values):
            raise ValueError("Select each site once")
        return values


class UsernameScanResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    site_name: str
    profile_url: str
    status: str
    http_status: int | None
    checked_at: datetime


class UsernameScanOut(BaseModel):
    id: str
    handle_id: str
    username: str
    site_names: list[str]
    created_at: datetime
    results: list[UsernameScanResultOut]


class SourceCreate(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=1, max_length=250)
    publisher: str = Field(default="", max_length=180)
    published_on: date | None = None
    retrieved_on: date = Field(default_factory=date.today)
    notes: str = Field(default="", max_length=5000)

    @field_validator("url")
    @classmethod
    def public_web_url_only(cls, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Source URL must use http or https")
        return value


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    url: str
    title: str
    publisher: str
    published_on: date | None
    retrieved_on: date
    notes: str


class FindingCreate(BaseModel):
    person_id: str
    source_id: str
    claim: str = Field(min_length=1, max_length=2000)
    excerpt: str = Field(default="", max_length=5000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Status = "unreviewed"


class RelationshipCreate(BaseModel):
    source_person_id: str
    target_person_id: str
    source_id: str
    label: str = Field(min_length=1, max_length=240)
    details: str = Field(default="", max_length=5000)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Status = "unreviewed"


class EvidenceOut(BaseModel):
    id: str
    title: str
    url: str
    retrieved_on: date


class FindingOut(BaseModel):
    id: str
    case_id: str
    person_id: str
    person_name: str
    source_id: str
    claim: str
    excerpt: str
    confidence: float
    status: Status
    created_at: datetime
    source: EvidenceOut


class RelationshipOut(BaseModel):
    id: str
    case_id: str
    source_person_id: str
    target_person_id: str
    source_id: str
    label: str
    details: str
    confidence: float
    status: Status
    created_at: datetime
    source: EvidenceOut


class AISettingsUpdate(BaseModel):
    provider_name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    model: str = Field(min_length=1, max_length=200)
    api_key: SecretStr = SecretStr("")
    enabled: bool = True

    @field_validator("provider_name", "base_url", "model")
    @classmethod
    def strip_ai_setting(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This setting cannot be blank")
        return value


class AISettingsOut(BaseModel):
    provider_name: str
    base_url: str
    model: str
    enabled: bool
    api_key_configured: bool
    source: Literal["local", "environment", "none"]


class AIAnalysisRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1500)
    source_ids: list[str] = Field(min_length=1, max_length=5)
    confirm_provider_share: bool = False

    @field_validator("question")
    @classmethod
    def nonblank_question(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Question cannot be blank")
        return value


class AISourceRef(BaseModel):
    id: str
    title: str
    url: str
    retrieved_on: date


class AIClaimOut(BaseModel):
    text: str
    source_ids: list[str]
    evidence_quote: str
    confidence: Literal["low", "medium", "high"]
    quote_verified: bool


class AIAnalysisOut(BaseModel):
    provider_name: str
    model: str
    summary: str
    claims: list[AIClaimOut]
    open_questions: list[str]
    sources: list[AISourceRef]
    saved: bool = False
    disclaimer: str


class GraphNode(BaseModel):
    id: str
    name: str
    aliases: list[str]
    notes: str
    findings_count: int


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    details: str
    confidence: float
    status: Status
    source_title: str
    source_url: str
    retrieved_on: date


class GraphOut(BaseModel):
    case_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    findings_count: int
    sources_count: int
