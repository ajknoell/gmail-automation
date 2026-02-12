import csv
import io
from typing import List, Dict, Tuple

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
                mapping['company'] = header

    return mapping

def validate_email(email: str) -> bool:
    """Basic email validation."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))
