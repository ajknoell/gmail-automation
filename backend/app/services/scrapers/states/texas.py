"""
Texas TDLR (Texas Department of Licensing and Regulation) scraper.

Scrapes the TDLR license search for tradespeople and contractors.
"""
import re
import logging
from datetime import date

from app.services.scrapers.base_scraper import BaseScraper, NormalizedBusiness

logger = logging.getLogger(__name__)

TDLR_LICENSE_TYPES = [
    'Air Conditioning and Refrigeration Contractor',
    'Electrician',
    'Plumber',
    'Property Tax Consultant',
    'Boiler',
    'Elevator/Escalator',
]

TDLR_SEARCH_URL = 'https://www.tdlr.texas.gov/LicenseSearch/'


class TexasTdlrScraper(BaseScraper):
    """Scraper for Texas Department of Licensing and Regulation."""

    @property
    def source_id(self) -> str:
        """Return unique source identifier."""
        return 'tdlr_tx'

    @property
    def source_name(self) -> str:
        """Return human-readable source name."""
        return 'Texas TDLR'

    def get_supported_license_types(self) -> list[str]:
        """Return TDLR license types."""
        return TDLR_LICENSE_TYPES

    def search(self, license_type: str, location: str, **kwargs) -> list[NormalizedBusiness]:
        """Search TDLR for licensed tradespeople.

        Args:
            license_type: TDLR license category
            location: Texas city or county
            **kwargs: max_results (default 50)

        Returns:
            List of normalized business records.
        """
        max_results = kwargs.get('max_results', 50)
        firecrawl = self._get_firecrawl()

        # TDLR search URL construction
        license_param = license_type.replace(' ', '+')
        search_url = (
            f"{TDLR_SEARCH_URL}?lictype={license_param}"
            f"&city={location.replace(' ', '+')}&state=TX"
        )

        try:
            result = firecrawl.scrape_url(search_url)
            if not result.get('success'):
                logger.warning(f"TDLR scrape failed: {result.get('error')}")
                return []

            markdown = result.get('markdown', '')
            return self._parse_tdlr_results(markdown, license_type, max_results)
        except Exception as e:
            logger.error(f"TDLR search error: {e}", exc_info=True)
            return []

    def _parse_tdlr_results(
        self,
        markdown: str,
        license_type: str,
        max_results: int,
    ) -> list[NormalizedBusiness]:
        """Parse TDLR search results into normalized records.

        Args:
            markdown: Page content from Firecrawl
            license_type: The license category searched
            max_results: Maximum results to return

        Returns:
            List of parsed business records.
        """
        businesses: list[NormalizedBusiness] = []

        # TDLR results contain license numbers in format: TACLBXXXXXXX or similar
        license_pattern = re.compile(r'(?:License|Lic)\s*#?\s*:?\s*([A-Z]{2,6}\d{5,10})', re.IGNORECASE)

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

        logger.info(f"TDLR parsed {len(businesses)} records for {license_type}")
        return businesses

    def _build_business(self, record: dict, license_type: str) -> NormalizedBusiness | None:
        """Build a NormalizedBusiness from parsed TDLR record.

        Args:
            record: Dict with license_number and lines
            license_type: TDLR license category

        Returns:
            NormalizedBusiness or None if insufficient data.
        """
        lines = record.get('lines', [])
        full_text = ' '.join(lines)

        name = None
        owner_name = None
        address = None
        phone = None
        status = 'active'

        for line in lines:
            if re.search(r'\b(active|inactive|expired|suspended)\b', line, re.IGNORECASE):
                status_match = re.search(r'\b(active|inactive|expired|suspended)\b', line, re.IGNORECASE)
                if status_match:
                    status = status_match.group(1).lower()

            # Business/company name
            name_match = re.search(r'(?:Company|Business|DBA)\s*:?\s*(.+)', line, re.IGNORECASE)
            if name_match and not name:
                name = name_match.group(1).strip()

            # Owner name
            owner_match = re.search(r'(?:Name|Owner|Licensee)\s*:?\s*(.+)', line, re.IGNORECASE)
            if owner_match and not owner_name:
                owner_name = owner_match.group(1).strip()

            # Phone
            phone_match = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', line)
            if phone_match and not phone:
                phone = phone_match.group(0)

        # Extract issue date
        issue_date = None
        date_match = re.search(r'(?:Issue|Original|Effective)\s*(?:Date)?[:\s]*(\d{1,2}/\d{1,2}/\d{4})', full_text, re.IGNORECASE)
        if date_match:
            try:
                parts = date_match.group(1).split('/')
                issue_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass

        # Use owner name as business name if no business name found
        if not name:
            name = owner_name
        if not name:
            return None

        return NormalizedBusiness(
            name=name,
            owner_name=owner_name,
            address=address,
            phone=phone,
            license_number=record['license_number'],
            license_type=license_type,
            license_status=status,
            license_issue_date=issue_date,
            source='tdlr_tx',
            source_url=TDLR_SEARCH_URL,
            raw_data={'license_type': license_type, 'text': full_text[:500]},
        )
