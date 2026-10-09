"""Pydantic API contracts."""

from typing import Any

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)


class MessageCreate(BaseModel):
    role: str = Field(default="user", pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SettingsUpdate(BaseModel):
    model_name: str | None = Field(default=None, max_length=120)
    web_search_enabled: bool | None = None
