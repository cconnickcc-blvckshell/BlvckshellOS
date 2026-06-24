"""Unit tests for the Upwork OAuth2 + GraphQL client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harness.config import Settings
from integrations.upwork_client import UpworkAPIError, UpworkAuthError, UpworkClient


def _settings(**overrides) -> Settings:
    defaults = {
        "upwork_client_id": "client-id",
        "upwork_client_secret": "client-secret",
        "upwork_refresh_token": "refresh-token",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_upwork_client_requires_credentials() -> None:
    with pytest.raises(UpworkAuthError):
        UpworkClient(Settings())


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


async def test_search_jobs_refreshes_token_and_parses_results() -> None:
    client = UpworkClient(_settings())

    token_resp = _mock_response(200, {"access_token": "tok-123", "expires_in": 3600})
    graphql_resp = _mock_response(
        200,
        {
            "data": {
                "marketplaceJobPostingsSearch": {
                    "edges": [
                        {
                            "node": {
                                "id": "job-1",
                                "title": "Build a CLI tool",
                                "description": "Need a Python CLI",
                                "category": "Web Dev",
                                "skills": ["python"],
                                "budget": {"amount": 500, "currencyCode": "USD"},
                                "engagementType": "FIXED",
                                "createdDateTime": "2026-06-24T00:00:00Z",
                            }
                        }
                    ]
                }
            }
        },
    )

    fake_http_client = AsyncMock()
    fake_http_client.post.side_effect = [token_resp, graphql_resp]
    fake_http_client.__aenter__.return_value = fake_http_client
    fake_http_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=fake_http_client):
        jobs = await client.search_jobs("python cli", limit=5)

    assert len(jobs) == 1
    assert jobs[0]["id"] == "job-1"
    assert jobs[0]["title"] == "Build a CLI tool"
    assert jobs[0]["budget_amount"] == 500
    assert jobs[0]["source"] == "upwork"


async def test_search_jobs_raises_on_token_failure() -> None:
    client = UpworkClient(_settings())

    token_resp = _mock_response(401, {"error": "invalid_grant"})
    fake_http_client = AsyncMock()
    fake_http_client.post.side_effect = [token_resp]
    fake_http_client.__aenter__.return_value = fake_http_client
    fake_http_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=fake_http_client):
        with pytest.raises(UpworkAuthError):
            await client.search_jobs("python cli")


async def test_search_jobs_raises_on_graphql_errors() -> None:
    client = UpworkClient(_settings())

    token_resp = _mock_response(200, {"access_token": "tok-123", "expires_in": 3600})
    graphql_resp = _mock_response(200, {"errors": [{"message": "bad query"}]})

    fake_http_client = AsyncMock()
    fake_http_client.post.side_effect = [token_resp, graphql_resp]
    fake_http_client.__aenter__.return_value = fake_http_client
    fake_http_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=fake_http_client):
        with pytest.raises(UpworkAPIError):
            await client.search_jobs("python cli")
