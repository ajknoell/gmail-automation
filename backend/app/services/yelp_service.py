"""
Yelp Fusion API service — searches for local businesses using the Yelp API.
Complements Google Places with ~20-30% additional coverage, especially strong
for restaurants, home services, and beauty/wellness.

Yelp Fusion API free tier: 5,000 calls/day.
Docs: https://docs.developer.yelp.com/reference/v3_business_search
"""
import hashlib
import time
import logging
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# In-memory caches with TTL
_yelp_search_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes

# Yelp category mapping to align with Google Places types
YELP_TO_GOOGLE_TYPE = {
    'restaurants': 'restaurant',
    'food': 'restaurant',
    'bars': 'bar',
    'nightlife': 'bar',
    'coffee': 'cafe',
    'bakeries': 'bakery',
    'beautysvc': 'beauty_salon',
    'hair': 'hair_care',
    'health': 'health',
    'dentists': 'dentist',
    'physicians': 'doctor',
    'autorepair': 'car_repair',
    'autobody': 'car_repair',
    'shopping': 'store',
    'homeservices': 'home_goods_store',
    'plumbing': 'plumber',
    'electricians': 'electrician',
    'hvac': 'hvac',
    'realestate': 'real_estate_agency',
    'financialservices': 'finance',
    'lawyers': 'lawyer',
    'petservices': 'pet_store',
    'gyms': 'gym',
    'education': 'school',
    'hotels': 'lodging',
}

# Reverse mapping: Google Places type → Yelp category alias
GOOGLE_TYPE_TO_YELP = {
    'restaurant': 'restaurants',
    'cafe': 'coffee',
    'bar': 'bars',
    'bakery': 'bakeries',
    'beauty_salon': 'beautysvc',
    'hair_care': 'hair',
    'spa': 'spas',
    'dentist': 'dentists',
    'doctor': 'physicians',
    'health': 'health',
    'car_repair': 'autorepair',
    'car_dealer': 'car_dealers',
    'store': 'shopping',
    'clothing_store': 'fashion',
    'jewelry_store': 'jewelry',
    'pet_store': 'pets',
    'gym': 'gyms',
    'lodging': 'hotels',
    'real_estate_agency': 'realestate',
    'lawyer': 'lawyers',
    'accounting': 'accountants',
    'plumber': 'plumbing',
    'electrician': 'electricians',
    'roofing_contractor': 'roofing',
    'painter': 'painters',
    'florist': 'florists',
    'veterinary_care': 'vet',
    'pharmacy': 'pharmacy',
    'school': 'education',
}


class YelpService:
    """Proxy for Yelp Fusion API v3."""

    BASE_URL = 'https://api.yelp.com/v3'

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            'Authorization': f'Bearer {api_key}',
            'Accept': 'application/json',
        }

    def search_businesses(
        self,
        lat: float,
        lng: float,
        radius: int = 5000,
        categories: Optional[str] = None,
        term: Optional[str] = None,
        min_rating: float = 0,
        max_results: int = 20,
    ) -> List[dict]:
        """
        Search for businesses using Yelp Fusion API.

        Args:
            lat, lng: Center coordinates
            radius: Search radius in meters (max 40,000)
            categories: Comma-separated Yelp category aliases (e.g., 'restaurants,bars')
            term: Free-text search term (e.g., 'plumber', 'vegan bakery')
            min_rating: Minimum Yelp rating (0-5)
            max_results: Max businesses to return (max 50 per API call)

        Returns:
            List of normalized business dicts matching Google Places format.
        """
        cache_key = hashlib.md5(
            f'yelp:{lat},{lng},{radius},{categories},{term},{min_rating}'.encode()
        ).hexdigest()
        cached = _yelp_search_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['results']

        params = {
            'latitude': lat,
            'longitude': lng,
            'radius': min(radius, 40000),  # Yelp max is 40km
            'limit': min(max_results, 50),
            'sort_by': 'distance',
        }
        if categories:
            params['categories'] = categories
        if term:
            params['term'] = term

        try:
            resp = requests.get(
                f'{self.BASE_URL}/businesses/search',
                headers=self.headers,
                params=params,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as e:
            logger.error(f'Yelp API error: {e.response.status_code} — {e.response.text[:200]}')
            return []
        except Exception as e:
            logger.error(f'Yelp API request failed: {e}')
            return []

        results = []
        for biz in data.get('businesses', []):
            rating = biz.get('rating', 0)
            if min_rating and rating < min_rating:
                continue

            # Map Yelp categories to a primary type
            yelp_categories = biz.get('categories', [])
            category_aliases = [c.get('alias', '') for c in yelp_categories]
            primary_type = ''
            for alias in category_aliases:
                if alias in YELP_TO_GOOGLE_TYPE:
                    primary_type = YELP_TO_GOOGLE_TYPE[alias]
                    break
            if not primary_type and yelp_categories:
                primary_type = yelp_categories[0].get('title', '')

            location = biz.get('location', {})
            address_parts = [
                location.get('address1', ''),
                location.get('city', ''),
                location.get('state', ''),
                location.get('zip_code', ''),
            ]
            formatted_address = ', '.join(p for p in address_parts if p)

            coords = biz.get('coordinates', {})

            results.append({
                'place_id': f'yelp_{biz.get("id", "")}',
                'name': biz.get('name', ''),
                'address': formatted_address,
                'lat': coords.get('latitude'),
                'lng': coords.get('longitude'),
                'rating': rating,
                'user_ratings_total': biz.get('review_count', 0),
                'types': category_aliases,
                'primary_type': primary_type,
                'phone': biz.get('display_phone', '') or biz.get('phone', ''),
                'website': '',  # Yelp API doesn't return website in search
                'business_status': 'OPERATIONAL' if not biz.get('is_closed') else 'CLOSED',
                'source': 'yelp',
                'yelp_url': biz.get('url', ''),
                'yelp_price': biz.get('price', ''),
                'yelp_image_url': biz.get('image_url', ''),
            })

        _yelp_search_cache[cache_key] = {'results': results, 'ts': time.time()}
        return results

    def get_business_details(self, yelp_id: str) -> Optional[dict]:
        """
        Get detailed info for a single business (includes website, hours, photos).

        The search endpoint doesn't return website URLs, so this is needed
        to get full details for enrichment.
        """
        try:
            resp = requests.get(
                f'{self.BASE_URL}/businesses/{yelp_id}',
                headers=self.headers,
                timeout=10,
            )
            resp.raise_for_status()
            biz = resp.json()

            return {
                'website': biz.get('url', ''),  # Yelp page URL
                'actual_website': '',  # Yelp doesn't expose this
                'phone': biz.get('display_phone', ''),
                'hours': biz.get('hours', []),
                'photos': biz.get('photos', []),
                'is_claimed': biz.get('is_claimed', False),
                'price': biz.get('price', ''),
            }
        except Exception as e:
            logger.warning(f'Yelp business detail failed for {yelp_id}: {e}')
            return None

    @staticmethod
    def google_type_to_yelp_category(google_type: str) -> str:
        """Convert a Google Places type to a Yelp category alias."""
        return GOOGLE_TYPE_TO_YELP.get(google_type, '')

    @staticmethod
    def google_types_to_yelp_categories(google_types: list) -> str:
        """Convert a list of Google Places types to comma-separated Yelp categories."""
        yelp_cats = []
        for gt in google_types:
            yc = GOOGLE_TYPE_TO_YELP.get(gt)
            if yc:
                yelp_cats.append(yc)
        return ','.join(yelp_cats) if yelp_cats else ''
