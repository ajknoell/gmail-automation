import hashlib
import time
from typing import Dict, List, Optional

import requests


# In-memory caches with TTL
_geocode_cache: Dict[str, dict] = {}
_nearby_cache: Dict[str, dict] = {}
_text_search_cache: Dict[str, dict] = {}
_CACHE_TTL = 600  # 10 minutes


class PlacesService:
    """Proxy for Google Maps Platform APIs (Geocoding + Places New)."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def geocode(self, address: str) -> Optional[dict]:
        """Convert an address/city name to lat/lng using Google Geocoding API.

        Returns {'lat': float, 'lng': float, 'formatted_address': str} or None.
        """
        cache_key = hashlib.md5(address.lower().strip().encode()).hexdigest()
        cached = _geocode_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['result']

        resp = requests.get(
            'https://maps.googleapis.com/maps/api/geocode/json',
            params={'address': address, 'key': self.api_key},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get('status') != 'OK' or not data.get('results'):
            return None

        result = data['results'][0]
        loc = result['geometry']['location']
        out = {
            'lat': loc['lat'],
            'lng': loc['lng'],
            'formatted_address': result.get('formatted_address', address),
        }
        _geocode_cache[cache_key] = {'result': out, 'ts': time.time()}
        return out

    def search_nearby(
        self,
        lat: float,
        lng: float,
        radius: int = 5000,
        included_type: str = '',
        keyword: str = '',
        min_rating: float = 0,
        max_results: int = 20,
    ) -> List[dict]:
        """Search for businesses using Places API (New) searchNearby.

        Uses POST https://places.googleapis.com/v1/places:searchNearby
        Returns list of normalized business dicts.
        """
        cache_key = hashlib.md5(
            f'{lat},{lng},{radius},{included_type},{keyword},{min_rating}'.encode()
        ).hexdigest()
        cached = _nearby_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['results']

        body: dict = {
            'locationRestriction': {
                'circle': {
                    'center': {'latitude': lat, 'longitude': lng},
                    'radius': float(radius),
                }
            },
            'maxResultCount': min(max_results, 20),
        }
        if included_type:
            body['includedTypes'] = [included_type]

        field_mask = ','.join([
            'places.id',
            'places.displayName',
            'places.formattedAddress',
            'places.location',
            'places.rating',
            'places.userRatingCount',
            'places.types',
            'places.nationalPhoneNumber',
            'places.internationalPhoneNumber',
            'places.websiteUri',
            'places.businessStatus',
            'places.primaryType',
        ])

        resp = requests.post(
            'https://places.googleapis.com/v1/places:searchNearby',
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': field_mask,
            },
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for place in data.get('places', []):
            rating = place.get('rating', 0)
            if min_rating and rating < min_rating:
                continue

            results.append({
                'place_id': place.get('id', ''),
                'name': place.get('displayName', {}).get('text', ''),
                'address': place.get('formattedAddress', ''),
                'lat': place.get('location', {}).get('latitude'),
                'lng': place.get('location', {}).get('longitude'),
                'rating': rating,
                'user_ratings_total': place.get('userRatingCount', 0),
                'types': place.get('types', []),
                'primary_type': place.get('primaryType', ''),
                'phone': (
                    place.get('nationalPhoneNumber')
                    or place.get('internationalPhoneNumber', '')
                ),
                'website': place.get('websiteUri', ''),
                'business_status': place.get('businessStatus', ''),
            })

        _nearby_cache[cache_key] = {'results': results, 'ts': time.time()}
        return results

    def search_text(
        self,
        query: str,
        lat: float,
        lng: float,
        radius: int = 5000,
        min_rating: float = 0,
        max_results: int = 20,
    ) -> List[dict]:
        """Search for businesses using Places API (New) Text Search.

        Uses POST https://places.googleapis.com/v1/places:searchText
        Supports free-form queries like "vegan bakery" or "mobile dog groomer".
        Returns list of normalized business dicts.
        """
        cache_key = hashlib.md5(
            f'text:{query},{lat},{lng},{radius},{min_rating}'.encode()
        ).hexdigest()
        cached = _text_search_cache.get(cache_key)
        if cached and (time.time() - cached['ts']) < _CACHE_TTL:
            return cached['results']

        body: dict = {
            'textQuery': query,
            'locationBias': {
                'circle': {
                    'center': {'latitude': lat, 'longitude': lng},
                    'radius': float(radius),
                }
            },
            'maxResultCount': min(max_results, 20),
        }

        field_mask = ','.join([
            'places.id',
            'places.displayName',
            'places.formattedAddress',
            'places.location',
            'places.rating',
            'places.userRatingCount',
            'places.types',
            'places.nationalPhoneNumber',
            'places.internationalPhoneNumber',
            'places.websiteUri',
            'places.businessStatus',
            'places.primaryType',
        ])

        resp = requests.post(
            'https://places.googleapis.com/v1/places:searchText',
            headers={
                'Content-Type': 'application/json',
                'X-Goog-Api-Key': self.api_key,
                'X-Goog-FieldMask': field_mask,
            },
            json=body,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for place in data.get('places', []):
            rating = place.get('rating', 0)
            if min_rating and rating < min_rating:
                continue

            results.append({
                'place_id': place.get('id', ''),
                'name': place.get('displayName', {}).get('text', ''),
                'address': place.get('formattedAddress', ''),
                'lat': place.get('location', {}).get('latitude'),
                'lng': place.get('location', {}).get('longitude'),
                'rating': rating,
                'user_ratings_total': place.get('userRatingCount', 0),
                'types': place.get('types', []),
                'primary_type': place.get('primaryType', ''),
                'phone': (
                    place.get('nationalPhoneNumber')
                    or place.get('internationalPhoneNumber', '')
                ),
                'website': place.get('websiteUri', ''),
                'business_status': place.get('businessStatus', ''),
            })

        _text_search_cache[cache_key] = {'results': results, 'ts': time.time()}
        return results
