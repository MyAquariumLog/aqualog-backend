from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

MAX_MESSAGE_LENGTH = 2000


def _validate_message(value: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError("Message must not be empty")
    if len(trimmed) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"Message must be at most {MAX_MESSAGE_LENGTH} characters")
    return trimmed


class CreateJournalEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_at: datetime | None = None
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _validate_message(value)

    @field_validator("entry_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("entry_at must include timezone information")
        return value


class UpdateJournalEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_at: datetime | None = None
    message: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_message(value)

    @field_validator("entry_at")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("entry_at must include timezone information")
        return value

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> UpdateJournalEntryRequest:
        if self.entry_at is None and self.message is None:
            raise ValueError("At least one of entry_at or message must be provided")
        return self


class JournalEntryPayload(BaseModel):
    id: str
    aquarium_id: str
    entry_at: str
    message: str
    created_at: str
    updated_at: str


class JournalEntryResponse(BaseModel):
    success: bool
    request_id: str
    data: JournalEntryPayload


class JournalEntryListResponse(BaseModel):
    success: bool
    request_id: str
    data: list[JournalEntryPayload]
