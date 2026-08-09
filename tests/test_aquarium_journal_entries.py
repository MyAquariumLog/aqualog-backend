from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.app import create_app
from src.config import Settings


@pytest.fixture
def auth_settings(tmp_path):
    return Settings(
        app_env="test",
        oauth_issuer_url="https://auth.example.com/application/o/aqualog",
        oauth_audience="test-client-id",
        test_database_url=f"sqlite+pysqlite:///{tmp_path}/test-aquarium-journal.db",
    )


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "x-request-id": "req-journal"}


def _create_aquarium(client: TestClient, token: str) -> str:
    response = client.post(
        "/api/v1/aquariums",
        headers=_auth_header(token),
        json={"name": "Display Reef", "type": "reef", "volume": {"value": 200.0, "unit": "L"}},
    )
    assert response.status_code == 201
    return response.json()["data"]["id"]


def test_journal_entries_require_authentication(auth_settings):
    app = create_app(auth_settings)

    with TestClient(app) as client:
        assert (
            client.post(
                "/api/v1/aquariums/aq-1/journal",
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "Water change"},
            ).status_code
            == 401
        )
        assert client.get("/api/v1/aquariums/aq-1/journal").status_code == 401


def test_journal_create_list_get_happy_path(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-owner", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            create_response = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={
                    "entry_at": "2026-07-01T12:00:00.987654Z",
                    "message": "  Did a 20% water change  ",
                },
            )
            assert create_response.status_code == 201
            created = create_response.json()["data"]
            assert created["aquarium_id"] == aquarium_id
            assert created["message"] == "Did a 20% water change"
            assert created["entry_at"].endswith("+00:00")
            assert "." not in created["entry_at"]
            assert set(create_response.json().keys()) == {"success", "request_id", "data"}
            assert create_response.json()["success"] is True
            assert create_response.json()["request_id"] == "req-journal"

            second_response = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:05:00Z", "message": "Dosed alkalinity"},
            )
            assert second_response.status_code == 201

            list_response = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
            )
            assert list_response.status_code == 200
            payload = list_response.json()
            assert isinstance(payload["data"], list)
            assert [item["message"] for item in payload["data"]] == [
                "Did a 20% water change",
                "Dosed alkalinity",
            ]

            entry_id = created["id"]
            get_response = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
            )
            assert get_response.status_code == 200
            assert get_response.json()["data"]["id"] == entry_id


def test_journal_list_empty_result(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-empty", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            list_response = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
            )
            assert list_response.status_code == 200
            assert list_response.json()["data"] == []


def test_journal_create_validation_errors(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-validator", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            missing_message = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z"},
            )
            assert missing_message.status_code == 422

            empty_message = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "   "},
            )
            assert empty_message.status_code == 422

            overlength_message = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "x" * 2001},
            )
            assert overlength_message.status_code == 422

            missing_timezone = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00", "message": "No tz"},
            )
            assert missing_timezone.status_code == 422


def test_journal_create_without_entry_at_defaults_to_now(
    create_valid_token, auth_settings, mock_jwks
):
    token = create_valid_token(sub="journal-default-now", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            before = datetime.now(timezone.utc).replace(microsecond=0)
            created = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"message": "Logged without an explicit timestamp"},
            )
            after = datetime.now(timezone.utc).replace(microsecond=0)

            assert created.status_code == 201
            entry_at = datetime.fromisoformat(created.json()["data"]["entry_at"])
            assert before <= entry_at <= after + timedelta(seconds=1)

            explicit = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-01-01T00:00:00Z", "message": "Explicit timestamp"},
            )
            assert explicit.status_code == 201
            assert explicit.json()["data"]["entry_at"] == "2026-01-01T00:00:00+00:00"


def test_journal_multiple_entries_may_share_timestamp(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-same-ts", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            first = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "First note"},
            )
            assert first.status_code == 201

            second = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "Second note"},
            )
            assert second.status_code == 201


def test_journal_get_not_found(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-get-missing", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            response = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal/{uuid4()}",
                headers=_auth_header(token),
            )
            assert response.status_code == 404


def test_journal_update_message_and_timestamp(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-update", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            created = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "Original"},
            )
            entry_id = created.json()["data"]["id"]

            message_update = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={"message": "Updated message"},
            )
            assert message_update.status_code == 200
            updated = message_update.json()["data"]
            assert updated["message"] == "Updated message"
            assert updated["entry_at"] == "2026-07-01T12:00:00+00:00"

            timestamp_update = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-02T09:00:00Z"},
            )
            assert timestamp_update.status_code == 200
            updated_again = timestamp_update.json()["data"]
            assert updated_again["entry_at"] == "2026-07-02T09:00:00+00:00"
            assert updated_again["message"] == "Updated message"

            both_update = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-03T09:00:00Z", "message": "Final message"},
            )
            assert both_update.status_code == 200
            final = both_update.json()["data"]
            assert final["entry_at"] == "2026-07-03T09:00:00+00:00"
            assert final["message"] == "Final message"


def test_journal_update_validation_errors(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-update-validator", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            created = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "Original"},
            )
            entry_id = created.json()["data"]["id"]

            empty_payload = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={},
            )
            assert empty_payload.status_code == 422

            invalid_message = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={"message": "   "},
            )
            assert invalid_message.status_code == 422

            overlength_message = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
                json={"message": "x" * 2001},
            )
            assert overlength_message.status_code == 422


def test_journal_update_not_found(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-update-missing", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            response = client.patch(
                f"/api/v1/aquariums/{aquarium_id}/journal/{uuid4()}",
                headers=_auth_header(token),
                json={"message": "Nope"},
            )
            assert response.status_code == 404


def test_journal_delete_and_not_found(create_valid_token, auth_settings, mock_jwks):
    token = create_valid_token(sub="journal-delete", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, token)

            created = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "To delete"},
            )
            entry_id = created.json()["data"]["id"]

            deleted = client.delete(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
            )
            assert deleted.status_code == 200
            assert deleted.json()["data"] == {"id": entry_id, "deleted": True}

            after_delete = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
            )
            assert after_delete.status_code == 404

            second_delete = client.delete(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(token),
            )
            assert second_delete.status_code == 404


def test_journal_ownership_scoping_across_all_operations(
    create_valid_token, auth_settings, mock_jwks
):
    owner_token = create_valid_token(sub="journal-owner-scope", aud="test-client-id")
    other_token = create_valid_token(sub="journal-other-scope", aud="test-client-id")
    app = create_app(auth_settings)

    with patch("src.auth.get_jwks_keys") as mock_get_keys:
        mock_get_keys.return_value = mock_jwks
        with TestClient(app) as client:
            aquarium_id = _create_aquarium(client, owner_token)

            created = client.post(
                f"/api/v1/aquariums/{aquarium_id}/journal",
                headers=_auth_header(owner_token),
                json={"entry_at": "2026-07-01T12:00:00Z", "message": "Owner-only note"},
            )
            assert created.status_code == 201
            entry_id = created.json()["data"]["id"]

            assert (
                client.post(
                    f"/api/v1/aquariums/{aquarium_id}/journal",
                    headers=_auth_header(other_token),
                    json={"entry_at": "2026-07-01T12:05:00Z", "message": "Intruder note"},
                ).status_code
                == 404
            )

            assert (
                client.get(
                    f"/api/v1/aquariums/{aquarium_id}/journal",
                    headers=_auth_header(other_token),
                ).status_code
                == 404
            )

            assert (
                client.get(
                    f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                    headers=_auth_header(other_token),
                ).status_code
                == 404
            )

            assert (
                client.patch(
                    f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                    headers=_auth_header(other_token),
                    json={"message": "Hijacked"},
                ).status_code
                == 404
            )

            assert (
                client.delete(
                    f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                    headers=_auth_header(other_token),
                ).status_code
                == 404
            )

            # Owner's data remains intact and untouched by the other user's attempts.
            owner_get = client.get(
                f"/api/v1/aquariums/{aquarium_id}/journal/{entry_id}",
                headers=_auth_header(owner_token),
            )
            assert owner_get.status_code == 200
            assert owner_get.json()["data"]["message"] == "Owner-only note"
