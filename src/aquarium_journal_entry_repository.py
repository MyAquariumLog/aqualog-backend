from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from src.models import Aquarium, AquariumJournalEntry


class AquariumJournalEntryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        aquarium_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        entry_at: datetime,
        message: str,
    ) -> AquariumJournalEntry:
        if not self._is_owned_aquarium(aquarium_id, owner_user_id):
            raise ValueError("Aquarium not found")

        entry = AquariumJournalEntry(
            aquarium_id=aquarium_id,
            entry_at=entry_at,
            message=message,
        )
        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def list_by_aquarium(
        self, aquarium_id: uuid.UUID, owner_user_id: uuid.UUID
    ) -> list[AquariumJournalEntry]:
        if not self._is_owned_aquarium(aquarium_id, owner_user_id):
            raise ValueError("Aquarium not found")

        return (
            self.session.query(AquariumJournalEntry)
            .filter(AquariumJournalEntry.aquarium_id == aquarium_id)
            .order_by(AquariumJournalEntry.entry_at.asc())
            .all()
        )

    def get_by_id_and_aquarium(
        self, entry_id: uuid.UUID, aquarium_id: uuid.UUID, owner_user_id: uuid.UUID
    ) -> AquariumJournalEntry | None:
        if not self._is_owned_aquarium(aquarium_id, owner_user_id):
            raise ValueError("Aquarium not found")

        return (
            self.session.query(AquariumJournalEntry)
            .filter(
                AquariumJournalEntry.id == entry_id,
                AquariumJournalEntry.aquarium_id == aquarium_id,
            )
            .one_or_none()
        )

    def update_by_id_and_aquarium(
        self,
        entry_id: uuid.UUID,
        aquarium_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        updates: dict[str, datetime | str],
    ) -> AquariumJournalEntry | None:
        entry = self.get_by_id_and_aquarium(
            entry_id=entry_id, aquarium_id=aquarium_id, owner_user_id=owner_user_id
        )
        if entry is None:
            return None

        for key, value in updates.items():
            setattr(entry, key, value)

        self.session.add(entry)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def delete_by_id_and_aquarium(
        self, entry_id: uuid.UUID, aquarium_id: uuid.UUID, owner_user_id: uuid.UUID
    ) -> bool:
        entry = self.get_by_id_and_aquarium(
            entry_id=entry_id, aquarium_id=aquarium_id, owner_user_id=owner_user_id
        )
        if entry is None:
            return False

        self.session.delete(entry)
        self.session.commit()
        return True

    def _is_owned_aquarium(self, aquarium_id: uuid.UUID, owner_user_id: uuid.UUID) -> bool:
        return (
            self.session.query(Aquarium.id)
            .filter(Aquarium.id == aquarium_id, Aquarium.owner_user_id == owner_user_id)
            .first()
            is not None
        )
