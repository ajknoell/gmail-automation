"""
Florida DBPR (Department of Business and Professional Regulation) scraper.

Scrapes the DBPR license verification search for contractors and tradespeople.
"""
import re
import logging
from datetime import date

from app.services.scrapers.base_scraper import BaseScraper, NormalizedBusiness

logger = logging.getLogger(__name__)

DBPR_LICENSE_TYPES = [
    'Certified Air Conditioning Contractor',
    'Certified Plumbing Contractor',
    'Certified Electrical Contractor',
    'Certified Roofing Contractor',
    'Certified General Contractor',
    'Certified Building Contractor',
    'Certified Mechanical Contractor',
    'Certified Sheet Metal Contractor',
    'Certified Pool/Spa Contractor',
    'Certified Solar Contractor',
]

DBPR_SEARCH_URL = 'https://www.myfloridalicense.com/wl11.asp'


class FloridaDbprScraper(BaseScraper):
    """Scraper for Florida Department of Business and Professional Regulation."""

    @property
    def source_id(self) -> str:
        """Return unique source identifier."""
        return 'dbpr_fl'

    @property
    def source_name(self) -> str:
        """Return human-readable source name."""
        return 'Florida DBPR'

    def get_supported_license_types(self) -> list[str]:
        """Return DBPR license types."""
        return DBPR_LICENSE_TYPES

    def search(self, license_type: str, location: str, **kwargs) -> list[NormalizedBusiness]:
        """Search DBPR for licensed contractors.

        Args:
            license_type: DBPR license classification
            location: Florida city or county
            **kwargs: max_results (default 50)

        Returns:
            List of normalized business records.
        """
        max_results = kwargs.get('max_results', 50)
        firecrawl = self._get_firecrawl()

        # DBPR search URL — the site uses form POST but the results page
        # can be accessed via direct URL with query parameters
        license_param = license_type.replace(' ', '+')
        search_url = (
            f"https://www.myfloridalicense.com/wl11.asp?"
            f"mode=2&search=LicNbr&SID=&bession=&Type=&"
            f"LicenceNbr=&LName=&FName=&city={location.replace(' ', '+')}"
            f"&county=&category={license_param}"
        )

        try:
            result = firecrawl.scrape_url(search_url)
            if not result.get('success'):
                logger.warning(f"DBPR scrape failed: {result.get('error')}")
                return []

            markdown = result.get('markdown', '')
            return self._parse_dbpr_results(markdown, license_type, max_results)
        except Exception as e:
            logger.error(f"DBPR search error: {e}", exc_info=True)
            return []

    def _parse_dbpr_results(
        self,
        markdown: str,
        license_type: str,
        max_results: int,
    ) -> list[NormalizedBusiness]:
        """Parse DBPR search results into normalized records.

        Args:
            markdown: Page content from Firecrawl
            license_type: The license category searched
            max_results: Maximum results to return

        Returns:
            List of parsed business records.
        """
        businesses: list[NormalizedBusiness] = []

        # Florida license numbers typically: CAC1234567, EC1234567, CFC1234567, etc.
        license_pattern = re.compile(r'([A-Z]{2,4}\d{5,8})')

        lines = markdown.split('\n')
        current_record: dict = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lic_match = license_pattern.search(line)
            if lic_match:
                if current_record.get('license_number'):
                    biz = self._build_business(current_record, license_type)
                    if biz:
                        businesses.append(biz)
                        if len(businesses) >= max_results:
                            break

                current_record = {
                    'license_number': lic_match.group(1),
                    'lines': [line],
                }
            elif current_record:
                current_record.setdefault('lines', []).append(line)

        # Last record
        if current_record.get('license_number') and len(businesses) < max_results:
            biz = self._build_business(current_record, license_type)
            if biz:
                businesses.append(biz)

        logger.info(f"DBPR parsed {len(businesses)} records for {license_type}")
        return businesses

    def _build_business(self, record: dict, license_type: str) -> NormalizedBusiness | None:
        """Build a NormalizedBusiness from parsed DBPR record.

        Args:
            record: Dict with license_number and lines
            license_type: DBPR license classification

        Returns:
            NormalizedBusiness or None if insufficient data.
        """
        lines = record.get('lines', [])
        full_text = ' '.join(lines)

        name = None
        owner_name = None
        address = None
        status = 'active'

        for line in lines:
            # Status detection
            if re.search(r'\b(current|active|delinquent|inactive|expired|null.void)\b', line, re.IGNORECASE):
                status_match = re.search(r'\b(current|active|delinquent|inactive|expired)\b', line, re.IGNORECASE)
                if status_match:
                    raw_status = status_match.group(1).lower()
                    status = 'active' if raw_status == 'current' else raw_status

            # Business name
            biz_match = re.search(r'(?:Business|DBA|Company)\s*:?\s*(.+)', line, re.IGNORECASE)
            if biz_match and not name:
                name = biz_match.group(1).strip()

            # Licensee/owner name
            owner_match = re.search(r'(?:Licensee|Name|Qualifier)\s*:?\s*(.+)', line, re.IGNORECASE)
            if owner_match and not owner_name:
                owner_name = owner_match.group(1).strip()

            # Florida address patterns
            addr_match = re.search(r'(\d+\s+.+(?:FL|Florida)\s+\d{5})', line, re.IGNORECASE)
            if addr_match and not address:
                address = addr_match.group(1).strip()

        # Extract dates
        issue_date = None
        date_match = re.search(
            r'(?:Original|Issue|Effective)\s*(?:Date)?[:\s]*(\d{1,2}/\d{1,2}/\d{4})',
            full_text,
            re.IGNORECASE,
        )
        if date_match:
            try:
                parts = date_match.group(1).split('/')
                issue_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass

        if not name:
            name = owner_name
        if not name:
            return None

        return NormalizedBusiness(
            name=name,
            owner_name=owner_name,
            address=address,
            license_number=record['license_number'],
            license_type=license_type,
            license_status=status,
            license_issue_date=issue_date,
            source='dbpr_fl',
            source_url=DBPR_SEARCH_URL,
            raw_data={'license_type': license_type, 'text': full_text[:500]},
        )
