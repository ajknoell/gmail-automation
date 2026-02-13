"""
Category Normalizer
--------------------
Maps diverse category names from different broker sites to a set of
standardized categories. This ensures consistent filtering even when
BizBuySell calls it "Restaurant" and another site calls it "QSR" or
"Food & Beverage".

Uses a two-tier approach:
1. Built-in mapping of common synonyms (fast, no API needed)
2. Fuzzy matching for close-enough names (e.g., "Restaurants" → "Restaurant")
"""

import re
from difflib import SequenceMatcher

# ─── Standard Categories ─────────────────────────────────────────
# These are the canonical category names used in the system.

STANDARD_CATEGORIES = [
    'Restaurant',
    'Food & Beverage',
    'Retail',
    'E-Commerce',
    'Manufacturing',
    'Distribution & Wholesale',
    'Healthcare & Medical',
    'Professional Services',
    'Technology & Software',
    'Construction & Trades',
    'Auto & Transportation',
    'Beauty & Personal Care',
    'Fitness & Recreation',
    'Education & Training',
    'Cleaning & Maintenance',
    'Real Estate',
    'Hospitality & Lodging',
    'Gas Station & Convenience',
    'Franchise',
    'Home Services',
    'Financial Services',
    'Media & Entertainment',
    'Agriculture',
    'Laundromat & Dry Cleaning',
    'Childcare & Daycare',
    'Other',
]

# ─── Synonym Mapping ─────────────────────────────────────────────
# Maps lowercase synonyms/variants → standard category name.
# This is the primary matching mechanism.

_SYNONYM_MAP = {
    # Restaurant
    'restaurant': 'Restaurant',
    'restaurants': 'Restaurant',
    'qsr': 'Restaurant',
    'quick service restaurant': 'Restaurant',
    'fast food': 'Restaurant',
    'fast casual': 'Restaurant',
    'fine dining': 'Restaurant',
    'casual dining': 'Restaurant',
    'pizza': 'Restaurant',
    'pizzeria': 'Restaurant',
    'diner': 'Restaurant',
    'cafe': 'Restaurant',
    'café': 'Restaurant',
    'coffee shop': 'Restaurant',
    'bakery': 'Restaurant',
    'deli': 'Restaurant',
    'delicatessen': 'Restaurant',
    'catering': 'Restaurant',
    'ice cream': 'Restaurant',
    'juice bar': 'Restaurant',
    'bar & grill': 'Restaurant',
    'bar': 'Restaurant',
    'tavern': 'Restaurant',
    'pub': 'Restaurant',

    # Food & Beverage
    'food & beverage': 'Food & Beverage',
    'food and beverage': 'Food & Beverage',
    'food': 'Food & Beverage',
    'beverage': 'Food & Beverage',
    'food service': 'Food & Beverage',
    'food distribution': 'Food & Beverage',
    'grocery': 'Food & Beverage',
    'supermarket': 'Food & Beverage',
    'liquor store': 'Food & Beverage',
    'wine shop': 'Food & Beverage',

    # Retail
    'retail': 'Retail',
    'retail store': 'Retail',
    'retail business': 'Retail',
    'specialty retail': 'Retail',
    'clothing': 'Retail',
    'clothing store': 'Retail',
    'apparel': 'Retail',
    'gift shop': 'Retail',
    'jewelry': 'Retail',
    'pet store': 'Retail',
    'pet': 'Retail',
    'sporting goods': 'Retail',
    'hardware store': 'Retail',
    'furniture store': 'Retail',
    'convenience store': 'Retail',

    # E-Commerce
    'e-commerce': 'E-Commerce',
    'ecommerce': 'E-Commerce',
    'online retail': 'E-Commerce',
    'online business': 'E-Commerce',
    'internet business': 'E-Commerce',
    'online store': 'E-Commerce',
    'amazon': 'E-Commerce',
    'amazon fba': 'E-Commerce',
    'dropshipping': 'E-Commerce',
    'saas': 'Technology & Software',

    # Manufacturing
    'manufacturing': 'Manufacturing',
    'manufacturer': 'Manufacturing',
    'production': 'Manufacturing',
    'fabrication': 'Manufacturing',
    'machine shop': 'Manufacturing',
    'metalwork': 'Manufacturing',
    'woodworking': 'Manufacturing',
    'printing': 'Manufacturing',

    # Distribution & Wholesale
    'distribution': 'Distribution & Wholesale',
    'distribution & wholesale': 'Distribution & Wholesale',
    'distribution and wholesale': 'Distribution & Wholesale',
    'wholesale': 'Distribution & Wholesale',
    'wholesale distribution': 'Distribution & Wholesale',
    'import/export': 'Distribution & Wholesale',
    'import export': 'Distribution & Wholesale',
    'logistics': 'Distribution & Wholesale',
    'warehouse': 'Distribution & Wholesale',

    # Healthcare & Medical
    'healthcare': 'Healthcare & Medical',
    'healthcare & medical': 'Healthcare & Medical',
    'medical': 'Healthcare & Medical',
    'dental': 'Healthcare & Medical',
    'dental practice': 'Healthcare & Medical',
    'pharmacy': 'Healthcare & Medical',
    'home health': 'Healthcare & Medical',
    'home health care': 'Healthcare & Medical',
    'assisted living': 'Healthcare & Medical',
    'veterinary': 'Healthcare & Medical',
    'optometry': 'Healthcare & Medical',
    'medical practice': 'Healthcare & Medical',

    # Professional Services
    'professional services': 'Professional Services',
    'consulting': 'Professional Services',
    'accounting': 'Professional Services',
    'cpa': 'Professional Services',
    'legal': 'Professional Services',
    'law firm': 'Professional Services',
    'insurance': 'Professional Services',
    'insurance agency': 'Professional Services',
    'marketing': 'Professional Services',
    'advertising': 'Professional Services',
    'staffing': 'Professional Services',
    'staffing agency': 'Professional Services',
    'recruiting': 'Professional Services',
    'engineering': 'Professional Services',

    # Technology & Software
    'technology': 'Technology & Software',
    'technology & software': 'Technology & Software',
    'software': 'Technology & Software',
    'it services': 'Technology & Software',
    'it': 'Technology & Software',
    'tech': 'Technology & Software',
    'web development': 'Technology & Software',
    'app development': 'Technology & Software',
    'managed services': 'Technology & Software',
    'msp': 'Technology & Software',

    # Construction & Trades
    'construction': 'Construction & Trades',
    'construction & trades': 'Construction & Trades',
    'contractor': 'Construction & Trades',
    'general contractor': 'Construction & Trades',
    'plumbing': 'Construction & Trades',
    'electrical': 'Construction & Trades',
    'electrician': 'Construction & Trades',
    'hvac': 'Construction & Trades',
    'roofing': 'Construction & Trades',
    'painting': 'Construction & Trades',
    'paving': 'Construction & Trades',
    'landscaping': 'Construction & Trades',
    'landscape': 'Construction & Trades',

    # Auto & Transportation
    'auto': 'Auto & Transportation',
    'auto & transportation': 'Auto & Transportation',
    'automotive': 'Auto & Transportation',
    'auto body': 'Auto & Transportation',
    'auto body shop': 'Auto & Transportation',
    'auto repair': 'Auto & Transportation',
    'car wash': 'Auto & Transportation',
    'car dealership': 'Auto & Transportation',
    'trucking': 'Auto & Transportation',
    'transportation': 'Auto & Transportation',
    'towing': 'Auto & Transportation',
    'oil change': 'Auto & Transportation',
    'tire shop': 'Auto & Transportation',

    # Beauty & Personal Care
    'beauty': 'Beauty & Personal Care',
    'beauty & personal care': 'Beauty & Personal Care',
    'salon': 'Beauty & Personal Care',
    'hair salon': 'Beauty & Personal Care',
    'nail salon': 'Beauty & Personal Care',
    'spa': 'Beauty & Personal Care',
    'barbershop': 'Beauty & Personal Care',
    'barber shop': 'Beauty & Personal Care',
    'med spa': 'Beauty & Personal Care',
    'medspa': 'Beauty & Personal Care',

    # Fitness & Recreation
    'fitness': 'Fitness & Recreation',
    'fitness & recreation': 'Fitness & Recreation',
    'gym': 'Fitness & Recreation',
    'health club': 'Fitness & Recreation',
    'yoga studio': 'Fitness & Recreation',
    'martial arts': 'Fitness & Recreation',
    'recreation': 'Fitness & Recreation',
    'entertainment': 'Fitness & Recreation',
    'amusement': 'Fitness & Recreation',
    'bowling alley': 'Fitness & Recreation',

    # Education & Training
    'education': 'Education & Training',
    'education & training': 'Education & Training',
    'training': 'Education & Training',
    'tutoring': 'Education & Training',
    'school': 'Education & Training',
    'learning center': 'Education & Training',
    'driving school': 'Education & Training',

    # Cleaning & Maintenance
    'cleaning': 'Cleaning & Maintenance',
    'cleaning & maintenance': 'Cleaning & Maintenance',
    'janitorial': 'Cleaning & Maintenance',
    'commercial cleaning': 'Cleaning & Maintenance',
    'pressure washing': 'Cleaning & Maintenance',
    'window cleaning': 'Cleaning & Maintenance',
    'maid service': 'Cleaning & Maintenance',
    'maintenance': 'Cleaning & Maintenance',

    # Real Estate
    'real estate': 'Real Estate',
    'property management': 'Real Estate',
    'property': 'Real Estate',

    # Hospitality & Lodging
    'hospitality': 'Hospitality & Lodging',
    'hospitality & lodging': 'Hospitality & Lodging',
    'hotel': 'Hospitality & Lodging',
    'motel': 'Hospitality & Lodging',
    'inn': 'Hospitality & Lodging',
    'bed and breakfast': 'Hospitality & Lodging',
    'b&b': 'Hospitality & Lodging',
    'lodging': 'Hospitality & Lodging',

    # Gas Station & Convenience
    'gas station': 'Gas Station & Convenience',
    'gas station & convenience': 'Gas Station & Convenience',
    'fuel station': 'Gas Station & Convenience',
    'service station': 'Gas Station & Convenience',

    # Franchise
    'franchise': 'Franchise',
    'franchises': 'Franchise',

    # Home Services
    'home services': 'Home Services',
    'home improvement': 'Home Services',
    'pest control': 'Home Services',
    'pool service': 'Home Services',
    'moving company': 'Home Services',
    'storage': 'Home Services',

    # Financial Services
    'financial services': 'Financial Services',
    'accounting firm': 'Financial Services',
    'tax preparation': 'Financial Services',
    'bookkeeping': 'Financial Services',

    # Media & Entertainment
    'media': 'Media & Entertainment',
    'media & entertainment': 'Media & Entertainment',
    'publishing': 'Media & Entertainment',
    'photography': 'Media & Entertainment',
    'videography': 'Media & Entertainment',
    'sign shop': 'Media & Entertainment',

    # Agriculture
    'agriculture': 'Agriculture',
    'farming': 'Agriculture',
    'nursery': 'Agriculture',
    'garden center': 'Agriculture',

    # Laundromat & Dry Cleaning
    'laundromat': 'Laundromat & Dry Cleaning',
    'laundromat & dry cleaning': 'Laundromat & Dry Cleaning',
    'dry cleaning': 'Laundromat & Dry Cleaning',
    'dry cleaner': 'Laundromat & Dry Cleaning',
    'laundry': 'Laundromat & Dry Cleaning',

    # Childcare & Daycare
    'childcare': 'Childcare & Daycare',
    'childcare & daycare': 'Childcare & Daycare',
    'daycare': 'Childcare & Daycare',
    'day care': 'Childcare & Daycare',
    'preschool': 'Childcare & Daycare',
    'child care': 'Childcare & Daycare',
}


def normalize_category(raw_category):
    """
    Normalize a raw category string to a standard category.

    Returns (standard_name, confidence) where confidence is:
    - 1.0 for exact synonym match
    - 0.6-0.9 for fuzzy match
    - 0.0 if no match found (returns 'Other')
    """
    if not raw_category or not raw_category.strip():
        return 'Other', 0.0

    cleaned = raw_category.strip().lower()
    # Remove common prefixes/suffixes
    cleaned = re.sub(r'^(type|category|industry)\s*:\s*', '', cleaned)
    cleaned = cleaned.strip()

    # 1. Exact synonym match
    if cleaned in _SYNONYM_MAP:
        return _SYNONYM_MAP[cleaned], 1.0

    # 2. Check if raw category CONTAINS a synonym
    for synonym, standard in _SYNONYM_MAP.items():
        if len(synonym) > 3 and synonym in cleaned:
            return standard, 0.9

    # 3. Check if a synonym is contained in the raw category
    for synonym, standard in _SYNONYM_MAP.items():
        if len(synonym) > 3 and cleaned in synonym:
            return standard, 0.85

    # 4. Fuzzy matching against standard category names
    best_score = 0
    best_match = 'Other'
    for std_cat in STANDARD_CATEGORIES:
        score = SequenceMatcher(None, cleaned, std_cat.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = std_cat

    if best_score >= 0.6:
        return best_match, best_score

    # 5. Fuzzy match against synonyms
    for synonym, standard in _SYNONYM_MAP.items():
        score = SequenceMatcher(None, cleaned, synonym).ratio()
        if score >= 0.7 and score > best_score:
            best_score = score
            best_match = standard

    if best_score >= 0.6:
        return best_match, best_score

    return 'Other', 0.0


def normalize_categories_batch(raw_categories):
    """
    Normalize a list of raw category strings.
    Returns list of (raw, standard, confidence) tuples.
    """
    return [
        (raw, *normalize_category(raw))
        for raw in raw_categories
    ]


def get_standard_categories():
    """Return the list of standard category names."""
    return list(STANDARD_CATEGORIES)
