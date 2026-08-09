## ADDED Requirements

### Requirement: Journal entries are scoped to a user-owned aquarium
The system SHALL expose authenticated journal entry operations at `/aquariums/{aquarium_id}/journal`, and SHALL only create, list, retrieve, update, or delete journal entries for aquariums owned by the requesting authenticated user.

#### Scenario: Create journal entry for owned aquarium
- **WHEN** an authenticated user submits a valid journal entry to `POST /aquariums/{aquarium_id}/journal` for an aquarium they own
- **THEN** the system persists the journal entry associated with that aquarium

#### Scenario: Journal operations on non-owned aquarium are rejected
- **WHEN** an authenticated user submits a create, list, retrieve, update, or delete journal request for an aquarium owned by another user
- **THEN** the system rejects the request with a not-found or unauthorized result and does not create, expose, modify, or delete journal data

### Requirement: Journal entries are private to the owning user
The system SHALL NOT expose any journal entry to a user other than the owner of the aquarium the entry belongs to. There is no sharing or cross-user visibility of journal entries in this implementation.

#### Scenario: Other users cannot list or view another user's journal entries
- **WHEN** an authenticated user requests journal entries for an aquarium they do not own
- **THEN** the system does not return any journal entry data belonging to that aquarium

### Requirement: Journal entry payload requires a message; timestamp is optional and defaults to now
The system SHALL require a non-empty `message` for every journal entry and MUST reject payloads missing it. The `entry_at` timestamp is OPTIONAL: when omitted, the system SHALL default it to the current time at the moment the entry is created.

#### Scenario: Missing message is rejected
- **WHEN** an authenticated user submits a journal entry create request to `POST /aquariums/{aquarium_id}/journal` missing `message`
- **THEN** the system rejects the request with a validation error and does not persist an entry

#### Scenario: Entry defaults to the current time when entry_at is omitted
- **WHEN** an authenticated user submits a journal entry create request to `POST /aquariums/{aquarium_id}/journal` with `message` but without `entry_at`
- **THEN** the system persists the entry with `entry_at` set to the current time at creation, normalized the same way as an explicitly supplied timestamp

#### Scenario: Empty message is rejected
- **WHEN** an authenticated user submits a journal entry create request with an empty or whitespace-only `message`
- **THEN** the system rejects the request with a validation error and does not persist an entry

#### Scenario: Overlength message is rejected
- **WHEN** an authenticated user submits a journal entry create request with a `message` exceeding the system's maximum allowed length
- **THEN** the system rejects the request with a validation error and does not persist an entry

#### Scenario: Journal entry timestamp is normalized
- **WHEN** an authenticated user submits a journal entry with sub-second `entry_at` precision
- **THEN** the system truncates the timestamp to the nearest lower whole second before persistence

#### Scenario: Multiple entries may share the same timestamp
- **WHEN** an authenticated user submits a journal entry for an aquarium where another entry already exists at the same normalized `entry_at` second
- **THEN** the system persists the new entry without rejecting it as a duplicate

### Requirement: Users can retrieve journal entry history
The system SHALL provide an authenticated operation to retrieve all journal entries for a user-owned aquarium in chronological order.

#### Scenario: Journal history is returned in chronological order
- **WHEN** an authenticated user requests journal entries from `GET /aquariums/{aquarium_id}/journal` for an owned aquarium
- **THEN** the system returns the entries sorted by `entry_at` in ascending order

#### Scenario: Journal history retrieval does not require server pagination in v1
- **WHEN** an authenticated user requests journal entries from `GET /aquariums/{aquarium_id}/journal` for an owned aquarium
- **THEN** the system returns the full result set without server pagination metadata or page parameters

### Requirement: Users can retrieve a single journal entry by id
The system SHALL provide an authenticated operation to retrieve a single journal entry by id, scoped to a user-owned aquarium.

#### Scenario: Retrieve existing entry by id
- **WHEN** an authenticated user requests `GET /aquariums/{aquarium_id}/journal/{entry_id}` for an entry that exists on an aquarium they own
- **THEN** the system returns that journal entry's data

#### Scenario: Retrieve non-existent entry
- **WHEN** an authenticated user requests `GET /aquariums/{aquarium_id}/journal/{entry_id}` for an entry id that does not exist on that aquarium
- **THEN** the system returns a not-found result

### Requirement: Users can update their own journal entries
The system SHALL provide an authenticated operation to update the `entry_at` and/or `message` of an existing journal entry, scoped to a user-owned aquarium.

#### Scenario: Update message of existing entry
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` with a new `message` for an entry that exists on an aquarium they own
- **THEN** the system persists the updated `message` and leaves other fields unchanged

#### Scenario: Update timestamp of existing entry
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` with a new `entry_at` for an entry that exists on an aquarium they own
- **THEN** the system persists the updated, normalized `entry_at` and leaves other fields unchanged

#### Scenario: Update with empty payload is rejected
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` with neither `entry_at` nor `message` present
- **THEN** the system rejects the request with a validation error and does not modify the entry

#### Scenario: Update with invalid message is rejected
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` with an empty, whitespace-only, or overlength `message`
- **THEN** the system rejects the request with a validation error and does not modify the entry

#### Scenario: Update non-existent entry
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` for an entry id that does not exist on that aquarium
- **THEN** the system returns a not-found result and does not create or modify an entry

#### Scenario: Update entry on non-owned aquarium is rejected
- **WHEN** an authenticated user submits `PATCH /aquariums/{aquarium_id}/journal/{entry_id}` for an aquarium owned by another user
- **THEN** the system rejects the request with a not-found or unauthorized result and does not modify the entry

### Requirement: Users can delete their own journal entries
The system SHALL provide an authenticated operation to delete a journal entry by id, scoped to a user-owned aquarium.

#### Scenario: Delete existing entry
- **WHEN** an authenticated user requests `DELETE /aquariums/{aquarium_id}/journal/{entry_id}` for an entry that exists on an aquarium they own
- **THEN** the system deletes the entry and it is no longer returned by list or retrieve operations

#### Scenario: Delete non-existent entry
- **WHEN** an authenticated user requests `DELETE /aquariums/{aquarium_id}/journal/{entry_id}` for an entry id that does not exist on that aquarium
- **THEN** the system returns a not-found result and does not affect other entries

#### Scenario: Deleting an aquarium removes its journal entries
- **WHEN** an aquarium with existing journal entries is deleted
- **THEN** the system cascades the deletion to remove all of that aquarium's journal entries

### Requirement: Journal entry responses include required fields
The system SHALL return each journal entry with its id, aquarium id, `entry_at` timestamp, `message`, `created_at` timestamp, and `updated_at` timestamp.

#### Scenario: Created entry response includes required fields
- **WHEN** an authenticated user successfully creates a journal entry
- **THEN** the response includes the entry's id, aquarium id, `entry_at`, `message`, `created_at`, and `updated_at`

#### Scenario: Listed and retrieved entries include required fields
- **WHEN** an authenticated user lists or retrieves journal entries
- **THEN** each returned entry includes id, aquarium id, `entry_at`, `message`, `created_at`, and `updated_at`

#### Scenario: Updated entry response reflects the change
- **WHEN** an authenticated user successfully updates a journal entry
- **THEN** the response includes the updated `entry_at` and/or `message`, and an `updated_at` timestamp later than `created_at`
