"""
State License Scraper — orchestrator that routes to the correct state-specific
scraper implementation. Entry point for all state licensing database searches.
"""
import logging
from typing import Optional

from app.services.scrapers.base_scraper import BaseScraper, NormalizedBusiness

logger = logging.getLogger(__name__)

# Registry of state scrapers, populated lazily
_SCRAPERS: dict[str, BaseScraper] = {}


def _ensure_registry() -> None:
    """Lazily import and register state scrapers."""
    if _SCRAPERS:
        return

    from app.services.scrapers.states.california import CaliforniaCslbScraper
    from app.services.scrapers.states.texas import TexasTdlrScraper
    from app.services.scrapers.states.florida import FloridaDbprScraper

    for scraper_cls in [CaliforniaCslbScraper, TexasTdlrScraper, FloridaDbprScraper]:
        scraper = scraper_cls()
        _SCRAPERS[scraper.source_id] = scraper


def get_available_states() -> list[dict]:
    """Return list of available state scrapers with their metadata.

    Returns:
        List of dicts with source_id, source_name, and supported_license_types.
    """
    _ensure_registry()
    return [
        {
            'source_id': s.source_id,
            'source_name': s.source_name,
            'license_types': s.get_supported_license_types(),
        }
        for s in _SCRAPERS.values()
    ]


def get_scraper(source_id: str) -> Optional[BaseScraper]:
    """Get a specific state scraper by source ID.

    Args:
        source_id: Scraper identifier (e.g., 'cslb_ca')

    Returns:
        Scraper instance or None if not found.
    """
    _ensure_registry()
    return _SCRAPERS.get(source_id)


def search_state_licenses(
    state_source_id: str,
    license_type: str,
    location: str,
    **kwargs,
) -> list[NormalizedBusiness]:
    """Search a state licensing database for businesses.

    Args:
        state_source_id: Which state scraper to use (e.g., 'cslb_ca')
        license_type: License classification to search
        location: City, county, or zip code
        **kwargs: Additional scraper-specific parameters

    Returns:
        List of normalized business records.
    """
    scraper = get_scraper(state_source_id)
    if not scraper:
        logger.error(f"No scraper registered for source_id={state_source_id}")
        return []

    try:
        results = scraper.search(license_type, location, **kwargs)
        logger.info(
            f"State license search: source={state_source_id} type={license_type} "
            f"location={location} results={len(results)}"
        )
        return results
    except Exception as e:
        logger.error(f"State license search failed: {e}", exc_info=True)
        return []
