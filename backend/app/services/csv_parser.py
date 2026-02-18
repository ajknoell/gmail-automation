import csv
import io
import re
from typing import List, Dict, Tuple, Optional

def parse_csv(file_content: bytes) -> Tuple[List[str], List[Dict]]:
    """Parse CSV file and return headers and rows."""
    # Handle BOM and different encodings
    for encoding in ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']:
        try:
            text = file_content.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        text = file_content.decode('utf-8', errors='replace')

    reader = csv.DictReader(io.StringIO(text))
    headers = reader.fieldnames or []
    # Strip whitespace from headers
    headers = [h.strip() for h in headers]
    # Re-parse with cleaned headers
    reader = csv.DictReader(io.StringIO(text))
    rows = []
    for row in reader:
        cleaned = {k.strip(): v for k, v in row.items() if k}
        rows.append(cleaned)
    return headers, rows

def parse_excel(file_content: bytes) -> Tuple[List[str], List[Dict]]:
    """Parse Excel file using openpyxl."""
    import openpyxl
    from io import BytesIO

    wb = openpyxl.load_workbook(BytesIO(file_content))
    sheet = wb.active

    headers = [str(cell.value) if cell.value else '' for cell in sheet[1]]
    rows = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        row_dict = {}
        for i, value in enumerate(row):
            if i < len(headers) and headers[i]:
                row_dict[headers[i]] = str(value) if value else ''
        if any(row_dict.values()):
            rows.append(row_dict)

    return headers, rows

def parse_file(file_content: bytes, filename: str) -> Tuple[List[str], List[Dict]]:
    """Parse file based on extension."""
    filename_lower = filename.lower()
    if filename_lower.endswith('.csv'):
        return parse_csv(file_content)
    elif filename_lower.endswith(('.xlsx', '.xls')):
        return parse_excel(file_content)
    else:
        raise ValueError(f'Unsupported file format: {filename}')

def detect_field_mapping(headers: List[str]) -> Dict[str, str]:
    """Auto-detect common field mappings."""
    mapping = {}
    email_patterns = ['email', 'e-mail', 'mail', 'email_address', 'emailaddress', 'e_mail', 'recipient']
    name_patterns = ['name', 'full_name', 'fullname', 'contact', 'contact_name', 'first_name', 'firstname', 'person']
    company_patterns = ['company', 'organization', 'org', 'business', 'company_name', 'companyname', 'employer']
    # Exclude columns that contain URL/website data from being mapped as company name
    url_indicators = ['url', 'website', 'link', 'site', 'domain', 'homepage', 'webpage', 'uri']

    # Normalize headers for matching: strip whitespace, remove special chars for comparison
    for header in headers:
        lower = header.lower().strip()
        # Also create a normalized version without special chars for matching
        normalized = lower.replace('-', '_').replace(' ', '_')
        if any(p == lower or p == normalized or p in lower for p in email_patterns):
            if 'email' not in mapping:
                mapping['email'] = header
        elif any(p == lower or p == normalized or p in lower for p in name_patterns):
            if 'name' not in mapping:
                mapping['name'] = header
        elif any(p == lower or p == normalized or p in lower for p in company_patterns):
            if 'company' not in mapping:
                # Skip columns that look like URL fields (e.g. company_url, company_website)
                if any(ind in lower for ind in url_indicators):
                    continue
                mapping['company'] = header

    return mapping

US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC',
}

_ADDRESS_PATTERNS = ['address', 'business_address', 'street_address', 'mailing_address', 'location']


def detect_address_column(headers: List[str]) -> Optional[str]:
    """Detect a column that contains a full address."""
    for header in headers:
        lower = header.lower().strip().replace('-', '_').replace(' ', '_')
        if any(p == lower or p in lower for p in _ADDRESS_PATTERNS):
            return header
    return None


def parse_address(address: str) -> Dict[str, str]:
    """Parse a US address string into street, city, state, and zip components.

    Handles formats like:
      "123 Main St, Austin, TX 78701"
      "123 Main St, Suite 200, Austin, TX"
      "123 Main St, Austin, Texas 78701"
    """
    if not address or not address.strip():
        return {}

    # Full state name -> abbreviation for common cases
    state_names = {
        'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
        'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
        'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
        'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
        'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
        'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
        'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
        'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
        'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
        'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
        'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
        'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
        'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
        'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
        'district of columbia': 'DC',
    }

    parts = [p.strip() for p in address.split(',')]

    if len(parts) < 2:
        return {'street': address.strip()}

    # Last part should contain state (+ optional zip)
    last = parts[-1].strip()
    # Try to extract state abbreviation and zip from last segment
    # e.g. "TX 78701" or "TX" or "Texas 78701"
    m = re.match(r'^([A-Za-z]{2})\s+(\d{5}(?:-\d{4})?)$', last)
    if m and m.group(1).upper() in US_STATES:
        state = m.group(1).upper()
        zip_code = m.group(2)
        city = parts[-2].strip()
        street = ', '.join(parts[:-2]).strip()
    elif last.upper() in US_STATES:
        state = last.upper()
        zip_code = ''
        city = parts[-2].strip()
        street = ', '.join(parts[:-2]).strip()
    else:
        # Try full state name: "Texas 78701" or "Texas"
        found_state = None
        found_zip = ''
        last_lower = last.lower()
        for name, abbr in state_names.items():
            if last_lower.startswith(name):
                found_state = abbr
                remainder = last[len(name):].strip()
                zip_m = re.match(r'^(\d{5}(?:-\d{4})?)$', remainder)
                if zip_m:
                    found_zip = zip_m.group(1)
                break
        if found_state:
            state = found_state
            zip_code = found_zip
            city = parts[-2].strip()
            street = ', '.join(parts[:-2]).strip()
        else:
            # Can't parse state — return the whole thing as street
            return {'street': address.strip()}

    result = {}
    if street:
        result['street'] = street
    if city:
        result['city'] = city
    if state:
        result['state'] = state
    if zip_code:
        result['zip'] = zip_code
    return result


def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))
