## Context

The backend already follows a consistent router-per-resource / repository-pattern / response-envelope architecture (see `src/routers/aquariums.py`, `src/aquarium_repository.py`, `src/routers/aquarium_measurements.py`). Aquarium measurements are the closest existing analog to a journal entry: both are timestamped, owner-scoped records nested under an aquarium. Unlike measurements, journal entries have no parameter/unit catalog, no numeric validation, and no canonical-vs-raw distinction — they are just a timestamp and free text.

## Goals / Non-Goals

**Goals:**
- Let an authenticated user create, list, retrieve, update, and delete journal entries for an aquarium they own.
- Keep the data model deliberately minimal: `entry_at` (timestamp) + `message` (text).
- Reuse existing conventions exactly (router factory, repository pattern, response envelope, ownership scoping via `owner_user_id` on the parent aquarium) so the capability is a drop-in peer of the existing resources.

**Non-Goals:**
- No sharing, collaboration, or multi-user visibility of journal entries (private-only, per the proposal).
- No tagging, categorization, activity types, or structured fields for specific activities (e.g. no dedicated "water change" schema) — free text only, in this iteration.
- No attachments/images.
- No edit history/versioning of journal entries — updates overwrite in place, only the current state is retained.
- No full-text search or pagination of journal history in v1 — mirrors the existing measurement-history precedent of returning the full filtered set.

## Decisions

- **Model shape**: New `AquariumJournalEntry` table: `id` (UUID PK), `aquarium_id` (FK → `aquariums.id`, `ondelete=CASCADE`, indexed), `entry_at` (`DateTime(timezone=True)`, required), `message` (`String`, required, reasonable max length e.g. 2000 chars), `created_at`/`updated_at` (existing `_utc_now` convention). No `owner_user_id` column on the entry itself — ownership is derived transitively through `aquarium.owner_user_id`, matching how `AquariumParameterThreshold`/`AquariumMeasurement` scope through `aquarium_id` rather than duplicating owner on every child row.
- **Timestamp normalization**: Reuse the existing measurement convention of truncating `entry_at` to whole-second UTC on write (`_normalize_timestamp` pattern) for consistency, but — unlike measurements — do **not** enforce uniqueness on `(aquarium_id, entry_at)`. Multiple journal entries can legitimately share a timestamp (e.g. two notes logged in the same batch import), so no unique constraint is added.
- **`entry_at` is optional on create**: `CreateJournalEntryRequest.entry_at` is `datetime | None`. When omitted, the router defaults it to `datetime.now(timezone.utc)` before the same normalization step, so callers logging an activity "right now" don't need to compute and send a timestamp themselves. `message` remains the only strictly required field.
- **Routing**: `build_journal_router()` mounted at `/aquariums/{aquarium_id}/journal`, matching the `/aquariums/{aquarium_id}/measurements/{parameter}` nesting style. Endpoints: `POST /`, `GET /` (list, chronological), `GET /{entry_id}`, `PATCH /{entry_id}`, `DELETE /{entry_id}`. All require `get_current_user` and re-verify aquarium ownership via `AquariumRepository.get_by_id_and_owner` before touching journal data, exactly as `aquarium_measurements.py` does.
- **Editing**: `PATCH /{entry_id}` accepts a partial payload (`entry_at` and/or `message`, at least one required) and updates only the supplied fields, following the same partial-update shape as `AquariumRepository.update_by_id_and_owner`. `updated_at` is bumped via the existing `onupdate=_utc_now` column behavior. A supplied `entry_at` is normalized to whole-second UTC the same way as on create; `message` is re-validated (non-empty, max length) the same way as on create. No edit history/versioning is kept — the update overwrites the row in place.
- **Repository**: `AquariumJournalEntryRepository` scoped by `aquarium_id` (already ownership-checked at the router layer, consistent with `AquariumMeasurementRepository`) with `create`, `list_by_aquarium`, `get_by_id_and_aquarium`, `update_by_id_and_aquarium`, `delete_by_id_and_aquarium`.
- **Response envelope**: All endpoints return `success_response(...)`/`error_response(...)` per existing convention; no deviation.
- **Migration**: One new Alembic revision adding `aquarium_journal_entries`, generated via `task db-migration-new`.

## Risks / Trade-offs

- [No `owner_user_id` on the entry row itself] → Every journal query must join/filter through the parent aquarium's owner; mitigated by always resolving and validating the aquarium via `AquariumRepository.get_by_id_and_owner` first, identical to the existing measurement/threshold routers, so this is a well-trodden pattern rather than a new risk surface.
- [No message length or content validation beyond a max length] → Acceptable for v1 given "simple entries... whatever activities they want to track"; a max length (2000 chars) still bounds storage/API payload size.
- [No edit history/versioning] → An update permanently overwrites the prior `message`/`entry_at`, so a correction destroys the original text; acceptable for v1 since journal entries are simple personal notes, and versioning can be layered on later as an additive change if needed.

## Migration Plan

1. Add `AquariumJournalEntry` model to `src/models.py`.
2. Generate and review an Alembic migration (`task db-migration-new NAME="add_aquarium_journal_entries"`), verify cascade-delete FK behavior.
3. Add repository, schemas, router; register router in `src/app.py` alongside the other `build_x_router()` calls.
4. `task db-migrate` in dev; no data backfill needed (net-new table).
5. Rollback: standard `alembic downgrade` of the single new revision; no impact on existing tables/data.

## Open Questions

None outstanding.
