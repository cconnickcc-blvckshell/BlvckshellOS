"""Upwork API client — OAuth2 token refresh + GraphQL job search.

Credentials come exclusively from :class:`harness.config.Settings` (env vars).
The access token is cached only as an in-process attribute on this client —
never written to the Judgment Ledger, working memory, or any other store —
per the standing constraint "do not store credentials in agent memory."

The OAuth2 token endpoint and the ``marketplaceJobPostingsSearch`` GraphQL
query/field names below are Upwork's documented v3 API shape as of this
writing. Upwork's docs site blocks automated fetches from this environment,
so **confirm the exact endpoint URL and field names against the user's
registered developer app / GraphQL schema introspection before relying on
this in production.**
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from harness.config import Settings

_TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
_GRAPHQL_URL = "https://api.upwork.com/graphql"

_JOB_SEARCH_QUERY = """
query MarketplaceJobSearch($query: String, $first: Int) {
  marketplaceJobPostingsSearch(marketPlaceJobFilter: {searchExpression: $query}, first: $first) {
    edges {
      node {
        id
        title
        description
        category
        skills
        budget {
          amount
          currencyCode
        }
        engagementType
        createdDateTime
      }
    }
  }
}
"""


class UpworkAuthError(RuntimeError):
    """Raised when Upwork OAuth2 credentials are missing or rejected."""


class UpworkAPIError(RuntimeError):
    """Raised when the Upwork GraphQL API returns an error response."""


@dataclass(slots=True)
class _CachedToken:
    access_token: str
    expires_at: float


class UpworkClient:
    """Thin async wrapper over Upwork's OAuth2 + GraphQL job-search API."""

    def __init__(self, settings: Settings) -> None:
        if not settings.upwork_enabled:
            raise UpworkAuthError(
                "Upwork credentials are not configured "
                "(BLVCKSHELL_UPWORK_CLIENT_ID/SECRET/REFRESH_TOKEN)"
            )
        self._client_id = settings.upwork_client_id
        self._client_secret = settings.upwork_client_secret
        self._refresh_token = settings.upwork_refresh_token
        self._token: _CachedToken | None = None

    async def _access_token(self) -> str:
        """Return a valid access token, refreshing it if expired or absent."""
        if self._token and self._token.expires_at > time.monotonic() + 30:
            return self._token.access_token

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
        if resp.status_code != 200:
            raise UpworkAuthError(f"Upwork token refresh failed: {resp.status_code} {resp.text}")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise UpworkAuthError(f"Upwork token refresh response missing access_token: {data}")

        self._token = _CachedToken(
            access_token=access_token,
            expires_at=time.monotonic() + float(data.get("expires_in", 3600)),
        )
        return access_token

    async def search_jobs(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search open job postings matching a free-text query.

        Args:
            query: Free-text search expression (skills, keywords).
            limit: Max number of postings to return.

        Returns:
            A list of job posting dicts (id, title, description, category,
            skills, budget, engagement_type, created_at).
        """
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _GRAPHQL_URL,
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "query": _JOB_SEARCH_QUERY,
                    "variables": {"query": query, "first": limit},
                },
            )
        if resp.status_code != 200:
            raise UpworkAPIError(f"Upwork GraphQL request failed: {resp.status_code} {resp.text}")

        data = resp.json()
        if "errors" in data:
            raise UpworkAPIError(f"Upwork GraphQL errors: {data['errors']}")

        edges = (
            data.get("data", {}).get("marketplaceJobPostingsSearch", {}).get("edges", []) or []
        )
        jobs = []
        for edge in edges:
            node = edge.get("node", {})
            budget = node.get("budget") or {}
            jobs.append(
                {
                    "id": node.get("id"),
                    "title": node.get("title"),
                    "description": node.get("description"),
                    "category": node.get("category"),
                    "skills": node.get("skills") or [],
                    "budget_amount": budget.get("amount"),
                    "budget_currency": budget.get("currencyCode"),
                    "engagement_type": node.get("engagementType"),
                    "created_at": node.get("createdDateTime"),
                    "source": "upwork",
                }
            )
        return jobs
