"""
California CSLB (Contractors State License Board) scraper.

Scrapes https://www.cslb.ca.gov/onlineservices/checklicenseII/checklicense.aspx
for licensed contractors by trade classification and location.
"""
import re
import logging
from datetime import date

from app.services.scrapers.base_scraper import BaseScraper, NormalizedBusiness

logger = logging.getLogger(__name__)

# CSLB trade classifications relevant to acquisition targets
CSLB_LICENSE_TYPES = [
    'C-20 Warm-Air Heating, Ventilating and Air-Conditioning',
    'C-36 Plumbing',
    'C-10 Electrical',
    'C-39 Roofing',
    'C-2 Insulation and Acoustical',
    'C-16 Fire Protection',
    'C-38 Refrigeration',
    'C-43 Sheet Metal',
    'C-46 Solar',
    'C-4 Boiler, Hot Water Heating and Steam Fitting',
    'B General Building',
    'A General Engineering',
]

# CSLB search URL for Firecrawl
CSLB_SEARCH_URL = 'https://www.cslb.ca.gov/onlineservices/checklicenseII/checklicense.aspx'


class CaliforniaCslbScraper(BaseScraper):
    """Scraper for California Contractors State License Board."""

    @property
    def source_id(self) -> str:
        """Return unique source identifier."""
        return 'cslb_ca'

    @property
    def source_name(self) -> str:
        """Return human-readable source name."""
        return 'California CSLB'

    def get_supported_license_types(self) -> list[str]:
        """Return CSLB trade classifications."""
        return CSLB_LICENSE_TYPES

    def search(self, license_type: str, location: str, **kwargs) -> list[NormalizedBusiness]:
        """Search CSLB for licensed contractors.

        Uses Firecrawl to scrape CSLB search results. The CSLB website
        requires POST form submission, so we construct the search URL
        and parse the results page.

        Args:
            license_type: CSLB classification code (e.g., 'C-20')
            location: California city or county
            **kwargs: max_results (default 50)

        Returns:
            List of normalized contractor records.
        """
        max_results = kwargs.get('max_results', 50)
        firecrawl = self._get_firecrawl()

        # Extract classification code from full name (e.g., "C-20" from "C-20 Warm-Air...")
        class_code = license_type.split(' ')[0] if ' ' in license_type else license_type

        # CSLB has a public search — scrape the results page
        search_url = (
            f"https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/"
            f"CheckLicense.aspx?LicenseType=A&Classification={class_code}"
            f"&City={location.replace(' ', '+')}"
        )

        try:
            result = firecrawl.scrape_url(search_url)
            if not result.get('success'):
                logger.warning(f"CSLB scrape failed for {search_url}: {result.get('error')}")
                return []

            markdown = result.get('markdown', '')
            return self._parse_cslb_results(markdown, class_code, max_results)
        except Exception as e:
            logger.error(f"CSLB search error: {e}", exc_info=True)
            return []

    def _parse_cslb_results(
        self,
        markdown: str,
        class_code: str,
        max_results: int,
    ) -> list[NormalizedBusiness]:
        """Parse CSLB search results page markdown into normalized records.

        Args:
            markdown: Page content as markdown from Firecrawl
            class_code: The CSLB classification code searched
            max_results: Maximum number of results to return

        Returns:
            List of parsed contractor records.
        """
        businesses: list[NormalizedBusiness] = []

        # CSLB results typically contain license number, business name, address, status
        # Pattern: License # XXXXXXX | Business Name | City | Status
        license_pattern = re.compile(
            r'(?:License\s*#?\s*|Lic\s*#?\s*)(\d{6,8})',
            re.IGNORECASE,
        )

        # Split by license numbers to find individual records
        lines = markdown.split('\n')
        current_record: dict = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            lic_match = license_pattern.search(line)
            if lic_match:
                # Save previous record
                if current_record.get('license_number'):
                    biz = self._build_business(current_record, class_code)
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

        # Don't forget the last record
        if current_record.get('license_number') and len(businesses) < max_results:
            biz = self._build_business(current_record, class_code)
            if biz:
                businesses.append(biz)

        logger.info(f"CSLB parsed {len(businesses)} records for {class_code}")
        return businesses

    def _build_business(self, record: dict, class_code: str) -> NormalizedBusiness | None:
        """Build a NormalizedBusiness from parsed CSLB record lines.

        Args:
            record: Dict with license_number and lines from page parsing
            class_code: CSLB classification code

        Returns:
            NormalizedBusiness or None if insufficient data.
        """
        lines = record.get('lines', [])
        full_text = ' '.join(lines)

        # Try to extract business name (usually the first text after license number)
        name = None
        address = None
        status = 'active'

        for line in lines:
            # Look for status keywords
            if re.search(r'\b(active|inactive|expired|suspended|revoked)\b', line, re.IGNORECASE):
                status_match = re.search(
                    r'\b(active|inactive|expired|suspended|revoked)\b',
                    line,
                    re.IGNORECASE,
                )
                if status_match:
                    status = status_match.group(1).lower()

            # Extract name: typically the business entity name line
            if not name and not re.search(r'(?:License|Lic|Status|Class|Issue|Expire)', line, re.IGNORECASE):
                # Likely the business name line
                cleaned = re.sub(r'[|*#]', '', line).strip()
                if cleaned and len(cleaned) > 3:
                    name = cleaned

        # Extract issue date
        issue_date = None
        date_match = re.search(r'(?:Issue|Issued|Original)\s*(?:Date)?[:\s]*(\d{1,2}/\d{1,2}/\d{4})', full_text, re.IGNORECASE)
        if date_match:
            try:
                parts = date_match.group(1).split('/')
                issue_date = date(int(parts[2]), int(parts[0]), int(parts[1]))
            except (ValueError, IndexError):
                pass

        if not name:
            return None

        return NormalizedBusiness(
            name=name,
            address=address,
            license_number=record['license_number'],
            license_type=class_code,
            license_status=status,
            license_issue_date=issue_date,
            source='cslb_ca',
            source_url=f"https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx?LicNum={record['license_number']}",
            raw_data={'class_code': class_code, 'text': full_text[:500]},
        )
