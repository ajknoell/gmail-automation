"""
Unified business search — merges results from multiple sources (Google Places,
Yelp, future: BBB, Yellow Pages, industry directories) with deduplication.
"""
import re
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize a business name for fuzzy matching."""
    if not name:
        return ''
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [' llc', ' inc', ' corp', ' ltd', ' co', ' company', ' llp']:
        name = name.replace(suffix, '')
    # Remove punctuation and extra whitespace
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def _normalize_address(address: str) -> str:
    """Normalize an address for matching."""
    if not address:
        return ''
    addr = address.lower().strip()
    # Standardize common abbreviations
    replacements = {
        ' street': ' st',
        ' avenue': ' ave',
        ' boulevard': ' blvd',
        ' drive': ' dr',
        ' road': ' rd',
        ' lane': ' ln',
        ' court': ' ct',
        ' place': ' pl',
        ' suite': ' ste',
        ' north': ' n',
        ' south': ' s',
        ' east': ' e',
        ' west': ' w',
    }
    for full, abbr in replacements.items():
        addr = addr.replace(full, abbr)
    # Remove punctuation
    addr = re.sub(r'[^\w\s]', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr


def _names_match(name1: str, name2: str) -> bool:
    """Check if two business names likely refer to the same business."""
    n1 = _normalize_name(name1)
    n2 = _normalize_name(name2)
    if not n1 or not n2:
        return False
    # Exact match after normalization
    if n1 == n2:
        return True
    # One contains the other (handles "Joe's Pizza" vs "Joe's Pizza Restaurant")
    if n1 in n2 or n2 in n1:
        return True
    # Check word overlap (>= 80%)
    words1 = set(n1.split())
    words2 = set(n2.split())
    if not words1 or not words2:
        return False
    overlap = len(words1 & words2) / min(len(words1), len(words2))
    return overlap >= 0.8


def _addresses_match(addr1: str, addr2: str) -> bool:
    """Check if two addresses likely refer to the same location."""
    a1 = _normalize_address(addr1)
    a2 = _normalize_address(addr2)
    if not a1 or not a2:
        return False
    # Exact match
    if a1 == a2:
        return True
    # Check if street numbers match and first few words overlap
    nums1 = re.findall(r'\d+', a1)
    nums2 = re.findall(r'\d+', a2)
    if nums1 and nums2 and nums1[0] == nums2[0]:
        # Same street number — check word overlap
        words1 = set(a1.split())
        words2 = set(a2.split())
        overlap = len(words1 & words2) / min(len(words1), len(words2))
        return overlap >= 0.5
    return False


def _is_duplicate(biz: dict, existing: List[dict]) -> bool:
    """Check if a business is a duplicate of any in the existing list."""
    for ex in existing:
        if _names_match(biz.get('name', ''), ex.get('name', '')):
            # Same name — check if address also matches (or is close)
            if _addresses_match(biz.get('address', ''), ex.get('address', '')):
                return True
            # If no address on one side, treat name match as sufficient
            # (only for very specific names, not generic ones like "Pizza Hut")
            if not biz.get('address') or not ex.get('address'):
                return True
    return False


def _merge_business_data(google_biz: dict, yelp_biz: dict) -> dict:
    """Merge data from Google and Yelp for the same business, preferring Google."""
    merged = dict(google_biz)
    # Fill in missing fields from Yelp
    if not merged.get('phone') and yelp_biz.get('phone'):
        merged['phone'] = yelp_biz['phone']
    # Add Yelp-specific data
    merged['yelp_url'] = yelp_biz.get('yelp_url', '')
    merged['yelp_rating'] = yelp_biz.get('rating')
    merged['yelp_review_count'] = yelp_biz.get('user_ratings_total')
    merged['yelp_price'] = yelp_biz.get('yelp_price', '')
    merged['sources'] = ['google', 'yelp']
    return merged


def merge_results(google_results: List[dict], yelp_results: List[dict]) -> List[dict]:
    """
    Merge Google Places and Yelp results with deduplication.

    Strategy:
    - Start with all Google results (primary source)
    - For each Yelp result, check if it's a duplicate of a Google result
    - If duplicate: merge Yelp data into the Google entry
    - If unique: append as a new result with source='yelp'
    - Returns combined list sorted by rating (desc)
    """
    # Tag Google results with source
    for biz in google_results:
        if 'source' not in biz:
            biz['source'] = 'google'
            biz['sources'] = ['google']

    merged = list(google_results)

    yelp_added = 0
    yelp_merged = 0

    for yelp_biz in yelp_results:
        # Find matching Google result
        matched = False
        for i, existing in enumerate(merged):
            if _names_match(yelp_biz.get('name', ''), existing.get('name', '')):
                if _addresses_match(yelp_biz.get('address', ''), existing.get('address', '')):
                    # Merge Yelp data into existing Google result
                    merged[i] = _merge_business_data(existing, yelp_biz)
                    yelp_merged += 1
                    matched = True
                    break

        if not matched:
            # New business only found on Yelp
            yelp_biz['sources'] = ['yelp']
            merged.append(yelp_biz)
            yelp_added += 1

    logger.info(
        f'Merged {len(google_results)} Google + {len(yelp_results)} Yelp results: '
        f'{yelp_merged} merged, {yelp_added} new from Yelp, {len(merged)} total'
    )

    # Sort by rating descending (businesses on both sources tend to be higher quality)
    merged.sort(key=lambda b: (
        len(b.get('sources', [])),  # Multi-source businesses first
        b.get('rating', 0),
    ), reverse=True)

    return merged
