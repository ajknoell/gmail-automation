"""
Base scraper — abstract interface for all business discovery scrapers.
Each scraper normalizes results into NormalizedBusiness dataclass.
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class NormalizedBusiness:
    """Standardized business record shared across all scraper sources."""

    name: str
    owner_name: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    license_number: str | None = None
    license_type: str | None = None
    license_status: str | None = None  # active, expired, suspended
    license_issue_date: date | None = None
    employee_count: int | None = None
    source: str = ''  # 'cslb_ca', 'tdlr_tx', 'dbpr_fl', etc.
    source_url: str | None = None
    raw_data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dictionary, converting dates to ISO strings."""
        data = asdict(self)
        if self.license_issue_date:
            data['license_issue_date'] = self.license_issue_date.isoformat()
        return data


class BaseScraper(ABC):
    """Abstract base class for business discovery scrapers."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Unique identifier for this scraper source (e.g., 'cslb_ca')."""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name (e.g., 'California CSLB')."""

    @abstractmethod
    def search(self, license_type: str, location: str, **kwargs) -> list[NormalizedBusiness]:
        """Search for businesses by license type and location.

        Args:
            license_type: Type of license to search for (e.g., 'C-20 HVAC')
            location: City, county, or zip code to search within
            **kwargs: Scraper-specific parameters

        Returns:
            List of normalized business records.
        """

    @abstractmethod
    def get_supported_license_types(self) -> list[str]:
        """Return list of license types this scraper can search for."""

    def _get_firecrawl(self) -> 'FirecrawlService':
        """Get Firecrawl service instance for web scraping."""
        from app.services.firecrawl_service import FirecrawlService
        return FirecrawlService()
