"""Service for interacting with the Apollo.io API."""

from __future__ import annotations

import logging

import requests

from app.models import Settings

logger = logging.getLogger(__name__)

APOLLO_BASE_URL = "https://api.apollo.io/api/v1"
DEFAULT_PER_PAGE = 25
MAX_PER_PAGE = 100


class ApolloService:
    """Handles all Apollo.io API interactions."""

    @staticmethod
    def _get_api_key() -> str | None:
        """Retrieve the Apollo API key from settings."""
        return Settings.get('apollo_api_key')

    @staticmethod
    def _make_request(endpoint: str, payload: dict) -> dict:
        """Make a POST request to the Apollo API.

        Args:
            endpoint: API endpoint path (e.g., '/mixed_people/search').
            payload: JSON body for the request.

        Returns:
            Parsed JSON response.

        Raises:
            ValueError: If API key is not configured.
            requests.HTTPError: If Apollo returns an error status.
        """
        api_key = ApolloService._get_api_key()
        if not api_key:
            raise ValueError("Apollo API key not configured")

        payload['api_key'] = api_key
        response = requests.post(
            f"{APOLLO_BASE_URL}{endpoint}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def search_people(
        person_titles: list[str] | None = None,
        person_locations: list[str] | None = None,
        q_organization_domains: list[str] | None = None,
        q_keywords: str | None = None,
        page: int = 1,
        per_page: int = DEFAULT_PER_PAGE,
    ) -> dict:
        """Search for people in Apollo.

        Args:
            person_titles: Job title filters (e.g., ['CEO', 'CTO']).
            person_locations: Location filters (e.g., ['California']).
            q_organization_domains: Company domain filters.
            q_keywords: Free-text keyword search.
            page: Page number (1-based).
            per_page: Results per page (max 100).

        Returns:
            Dict with 'people' list and 'pagination' info.
        """
        per_page = min(per_page, MAX_PER_PAGE)
        payload: dict = {"page": page, "per_page": per_page}

        if person_titles:
            payload["person_titles"] = person_titles
        if person_locations:
            payload["person_locations"] = person_locations
        if q_organization_domains:
            payload["q_organization_domains"] = "\n".join(q_organization_domains)
        if q_keywords:
            payload["q_keywords"] = q_keywords

        return ApolloService._make_request("/mixed_people/search", payload)

    @staticmethod
    def map_to_contact(person: dict) -> dict:
        """Map Apollo person fields to Veloro contact fields.

        Args:
            person: Raw person dict from Apollo API response.

        Returns:
            Dict with standardized contact fields.
        """
        org = person.get("organization") or {}
        return {
            "email": person.get("email", ""),
            "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "company": org.get("name", ""),
            "website": org.get("website_url", ""),
            "phone": person.get("phone_number") or person.get("sanitized_phone") or "",
            "address": person.get("city") or "",
            "business_category": org.get("industry", ""),
            "title": person.get("title", ""),
            "linkedin_url": person.get("linkedin_url", ""),
            "apollo_id": person.get("id", ""),
        }
