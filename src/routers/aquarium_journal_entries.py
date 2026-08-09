from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.aquarium_journal_entry_repository import AquariumJournalEntryRepository
from src.aquarium_repository import AquariumRepository
from src.auth import get_current_user
from src.db import get_session
from src.models import AquariumJournalEntry
from src.responses import success_response
from src.schemas.aquarium_journal_entries import (
    CreateJournalEntryRequest,
    JournalEntryListResponse,
    JournalEntryResponse,
    UpdateJournalEntryRequest,
)
from src.user_service import AuthenticatedUser


def _normalize_timestamp(value: datetime) -> datetime:
    return value.astimezone(timezone.utc).replace(microsecond=0)


def _to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _to_payload(entry: AquariumJournalEntry) -> dict[str, str]:
    return {
        "id": str(entry.id),
        "aquarium_id": str(entry.aquarium_id),
        "entry_at": _to_utc_iso(entry.entry_at),
        "message": entry.message,
        "created_at": _to_utc_iso(entry.created_at),
        "updated_at": _to_utc_iso(entry.updated_at),
    }


def _get_owned_aquarium_or_404(
    aquarium_repo: AquariumRepository, aquarium_id: uuid.UUID, owner_user_id: uuid.UUID
):
    aquarium = aquarium_repo.get_by_id_and_owner(aquarium_id, owner_user_id)
    if aquarium is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Aquarium not found")
    return aquarium


def build_journal_router() -> APIRouter:
    router = APIRouter(prefix="/aquariums", tags=["aquarium-journal"])

    @router.post(
        "/{aquarium_id}/journal",
        response_model=JournalEntryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_journal_entry(
        aquarium_id: uuid.UUID,
        request: Request,
        payload: CreateJournalEntryRequest = Body(...),
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        request_id = getattr(request.state, "request_id", "unknown")
        aquarium_repo = AquariumRepository(session)
        aquarium = _get_owned_aquarium_or_404(aquarium_repo, aquarium_id, current_user.user.id)

        entry_at = payload.entry_at if payload.entry_at is not None else datetime.now(timezone.utc)

        journal_repo = AquariumJournalEntryRepository(session)
        entry = journal_repo.create(
            aquarium_id=aquarium.id,
            owner_user_id=current_user.user.id,
            entry_at=_normalize_timestamp(entry_at),
            message=payload.message,
        )

        return success_response(
            _to_payload(entry), request_id=request_id, status_code=status.HTTP_201_CREATED
        )

    @router.get("/{aquarium_id}/journal", response_model=JournalEntryListResponse)
    async def list_journal_entries(
        aquarium_id: uuid.UUID,
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        request_id = getattr(request.state, "request_id", "unknown")
        aquarium_repo = AquariumRepository(session)
        aquarium = _get_owned_aquarium_or_404(aquarium_repo, aquarium_id, current_user.user.id)

        journal_repo = AquariumJournalEntryRepository(session)
        entries = journal_repo.list_by_aquarium(aquarium.id, current_user.user.id)
        return success_response([_to_payload(entry) for entry in entries], request_id=request_id)

    @router.get("/{aquarium_id}/journal/{entry_id}", response_model=JournalEntryResponse)
    async def get_journal_entry(
        aquarium_id: uuid.UUID,
        entry_id: uuid.UUID,
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        request_id = getattr(request.state, "request_id", "unknown")
        aquarium_repo = AquariumRepository(session)
        aquarium = _get_owned_aquarium_or_404(aquarium_repo, aquarium_id, current_user.user.id)

        journal_repo = AquariumJournalEntryRepository(session)
        entry = journal_repo.get_by_id_and_aquarium(entry_id, aquarium.id, current_user.user.id)
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found"
            )

        return success_response(_to_payload(entry), request_id=request_id)

    @router.patch("/{aquarium_id}/journal/{entry_id}", response_model=JournalEntryResponse)
    async def update_journal_entry(
        aquarium_id: uuid.UUID,
        entry_id: uuid.UUID,
        request: Request,
        payload: UpdateJournalEntryRequest = Body(...),
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        request_id = getattr(request.state, "request_id", "unknown")
        aquarium_repo = AquariumRepository(session)
        aquarium = _get_owned_aquarium_or_404(aquarium_repo, aquarium_id, current_user.user.id)

        updates: dict[str, datetime | str] = {}
        if payload.entry_at is not None:
            updates["entry_at"] = _normalize_timestamp(payload.entry_at)
        if payload.message is not None:
            updates["message"] = payload.message

        journal_repo = AquariumJournalEntryRepository(session)
        entry = journal_repo.update_by_id_and_aquarium(
            entry_id=entry_id,
            aquarium_id=aquarium.id,
            owner_user_id=current_user.user.id,
            updates=updates,
        )
        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found"
            )

        return success_response(_to_payload(entry), request_id=request_id)

    @router.delete("/{aquarium_id}/journal/{entry_id}")
    async def delete_journal_entry(
        aquarium_id: uuid.UUID,
        entry_id: uuid.UUID,
        request: Request,
        current_user: AuthenticatedUser = Depends(get_current_user),
        session: Session = Depends(get_session),
    ):
        request_id = getattr(request.state, "request_id", "unknown")
        aquarium_repo = AquariumRepository(session)
        aquarium = _get_owned_aquarium_or_404(aquarium_repo, aquarium_id, current_user.user.id)

        journal_repo = AquariumJournalEntryRepository(session)
        deleted = journal_repo.delete_by_id_and_aquarium(
            entry_id=entry_id, aquarium_id=aquarium.id, owner_user_id=current_user.user.id
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found"
            )

        return success_response({"id": str(entry_id), "deleted": True}, request_id=request_id)

    return router
