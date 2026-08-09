## Why

Aquarium keepers routinely want to log free-form activities (water changes, dosing, equipment maintenance, observations) alongside their measurement history, but there is currently no way to record anything that isn't a structured parameter measurement. A simple, private journal lets users capture these events against an aquarium without waiting for dedicated structured capabilities for each activity type.

## What Changes

- Add a new **Journal** capability: authenticated users can create, list, retrieve, update, and delete free-form journal entries scoped to an aquarium they own.
- Each journal entry has an `entry_at` timestamp (date/time of the activity) and a `message` (free text describing the activity). `entry_at` is optional on create — if omitted, it defaults to the current time.
- Journal entries are private: only the owning user can create or view entries for their own aquariums. No sharing or cross-user visibility in this initial implementation.
- New `AquariumJournalEntry` model, `AquariumJournalEntryRepository`, and `build_journal_router()` following the existing router-per-resource/repository-pattern/response-envelope conventions.
- New Alembic migration adding the `aquarium_journal_entries` table.

## Capabilities

### New Capabilities
- `api-aquarium-journal`: Authenticated CRUD API for recording, retrieving, updating, and deleting private, free-form journal entries (timestamp + message) scoped to a user-owned aquarium.

### Modified Capabilities
(none — this is purely additive; no existing requirements change)

## Impact

- **Code**: new `src/models.py::AquariumJournalEntry`, `src/aquarium_journal_entry_repository.py`, `src/routers/aquarium_journal_entry_router.py` (or similar), request/response schemas, registration in `src/app.py`.
- **API**: new authenticated endpoints under `/api/v1/aquariums/{aquarium_id}/journal`.
- **Database**: new table `aquarium_journal_entries` with a foreign key to `aquariums` (cascade delete) and a new Alembic revision.
- **Tests**: new repository-level and router-level test files following the existing per-resource test split.
- **Dependencies**: none new.
