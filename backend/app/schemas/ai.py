from typing import Any, Literal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Conversation messages cannot be empty")
        return cleaned


class DatasetChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[ConversationTurn] = Field(default_factory=list, max_length=10)
    exploration_context: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def strip_message(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty")
        return cleaned


class DatasetChatResponse(BaseModel):
    answer: str
    dataset_id: int


class DatasetReportContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    executive_summary: str = Field(min_length=1, max_length=4000)
    key_findings: list[str] = Field(min_length=1, max_length=12)
    data_quality: str = Field(min_length=1, max_length=3000)
    trends: list[str] = Field(min_length=1, max_length=12)
    business_insights: list[str] = Field(min_length=1, max_length=12)
    recommendations: list[str] = Field(min_length=1, max_length=12)
    conclusion: str = Field(min_length=1, max_length=3000)

    @field_validator(
        "title",
        "executive_summary",
        "data_quality",
        "conclusion",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "key_findings",
        "trends",
        "business_insights",
        "recommendations",
        mode="before",
    )
    @classmethod
    def strip_list_items(cls, value: list[str]) -> list[str]:
        if not isinstance(value, list):
            return value
        return [item.strip() if isinstance(item, str) else item for item in value]


class DatasetReportResponse(DatasetReportContent):
    dataset_id: int
    dataset_name: str
    row_count: int
    column_count: int
    generated_at: datetime