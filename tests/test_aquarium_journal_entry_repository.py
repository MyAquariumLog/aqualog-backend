from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from conftest import register_engine_for_cleanup
from src.aquarium_journal_entry_repository import AquariumJournalEntryRepository
from src.aquarium_repository import AquariumRepository
from src.db import Base
from src.user_repository import UserRepository


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _build_repos(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path}/aquarium-journal-repo-test.db", future=True
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True, expire_on_commit=False)()
    register_engine_for_cleanup(session, engine)
    return (
        AquariumRepository(session),
        AquariumJournalEntryRepository(session),
        UserRepository(session),
        session,
    )


def test_journal_repository_create_and_list_chronological(tmp_path):
    aquarium_repo, journal_repo, user_repo, _ = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Display", aquarium_type="reef", volume_liters=200.0
    )

    second = journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc),
        message="Second entry",
    )
    first = journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        message="First entry",
    )

    entries = journal_repo.list_by_aquarium(aquarium.id, owner.id)
    assert [e.id for e in entries] == [first.id, second.id]


def test_journal_repository_get_by_id_found_and_not_found(tmp_path):
    aquarium_repo, journal_repo, user_repo, _ = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    other = user_repo.resolve_or_create("https://issuer.example.com", "other")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Nano", aquarium_type="reef", volume_liters=80.0
    )

    created = journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        message="Water change",
    )

    found = journal_repo.get_by_id_and_aquarium(created.id, aquarium.id, owner.id)
    assert found is not None
    assert found.message == "Water change"

    missing = journal_repo.get_by_id_and_aquarium(uuid4(), aquarium.id, owner.id)
    assert missing is None

    with pytest.raises(ValueError):
        journal_repo.get_by_id_and_aquarium(created.id, aquarium.id, other.id)


def test_journal_repository_update_partial_fields_and_bumps_updated_at(tmp_path):
    aquarium_repo, journal_repo, user_repo, _ = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Frag", aquarium_type="reef", volume_liters=120.0
    )
    created = journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        message="Original message",
    )
    original_updated_at = created.updated_at

    updated = journal_repo.update_by_id_and_aquarium(
        entry_id=created.id,
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        updates={"message": "Edited message"},
    )
    assert updated is not None
    assert updated.message == "Edited message"
    # SQLite drops tzinfo on round-trip; compare naive wall-clock values only.
    assert updated.entry_at.replace(tzinfo=timezone.utc) == created.entry_at.replace(
        tzinfo=timezone.utc
    )
    assert updated.updated_at >= original_updated_at

    new_timestamp = datetime(2026, 7, 3, 9, 0, 0, tzinfo=timezone.utc)
    updated_again = journal_repo.update_by_id_and_aquarium(
        entry_id=created.id,
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        updates={"entry_at": new_timestamp},
    )
    assert updated_again is not None
    assert updated_again.entry_at.replace(tzinfo=timezone.utc) == new_timestamp
    assert updated_again.message == "Edited message"


def test_journal_repository_update_not_found(tmp_path):
    aquarium_repo, journal_repo, user_repo, _ = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Tank", aquarium_type="reef", volume_liters=90.0
    )

    result = journal_repo.update_by_id_and_aquarium(
        entry_id=uuid4(),
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        updates={"message": "Nope"},
    )
    assert result is None


def test_journal_repository_delete_found_and_not_found(tmp_path):
    aquarium_repo, journal_repo, user_repo, _ = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Sump", aquarium_type="reef", volume_liters=50.0
    )
    created = journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        message="Dosed alkalinity",
    )

    assert journal_repo.delete_by_id_and_aquarium(created.id, aquarium.id, owner.id) is True
    assert journal_repo.delete_by_id_and_aquarium(created.id, aquarium.id, owner.id) is False


def test_journal_repository_cascade_deletes_with_aquarium(tmp_path):
    aquarium_repo, journal_repo, user_repo, session = _build_repos(tmp_path)
    owner = user_repo.resolve_or_create("https://issuer.example.com", "owner")
    aquarium = aquarium_repo.create(
        owner_user_id=owner.id, name="Cascade Tank", aquarium_type="reef", volume_liters=100.0
    )
    journal_repo.create(
        aquarium_id=aquarium.id,
        owner_user_id=owner.id,
        entry_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        message="Entry before delete",
    )

    assert aquarium_repo.delete_by_id_and_owner(aquarium.id, owner.id) is True

    from src.models import AquariumJournalEntry

    remaining = (
        session.query(AquariumJournalEntry)
        .filter(AquariumJournalEntry.aquarium_id == aquarium.id)
        .all()
    )
    assert remaining == []
