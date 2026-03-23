"""Find businesses in an area using Google Places API."""

import os
import time
import requests
from utils.cache import get_cached, set_cached

PLACES_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
CACHE_NAME = "places"


def search_businesses(business_type, location, api_key=None):
    """
    Search Google Places for businesses of a given type in a location.
    Returns up to 20 results with name, address, phone, website.
    """
    api_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
    if not api_key:
        print("ERROR: No Google API key. Set GOOGLE_API_KEY in .env")
        return []

    cache_key = f"{business_type}|{location}"
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        print(f"  (Using cached results for '{business_type}' in '{location}')")
        return cached

    query = f"{business_type} in {location}"
    print(f"  Searching Google Places for: {query}")

    params = {"query": query, "key": api_key}
    resp = requests.get(PLACES_SEARCH_URL, params=params)
    data = resp.json()

    if data.get("status") != "OK":
        print(f"  Places API error: {data.get('status')} - {data.get('error_message', '')}")
        return []

    results = []
    places = data.get("results", [])[:20]

    for i, place in enumerate(places):
        place_id = place.get("place_id")
        print(f"  [{i+1}/{len(places)}] {place.get('name', '?')}...", end=" ", flush=True)

        # Get details for phone and website
        details = _get_place_details(place_id, api_key)

        biz = {
            "name": place.get("name", ""),
            "address": details.get("formatted_address", place.get("formatted_address", "")),
            "phone": details.get("formatted_phone_number", ""),
            "website": details.get("website", ""),
            "place_id": place_id,
        }
        results.append(biz)

        phone_str = biz["phone"] or "no phone"
        print(phone_str)

        time.sleep(0.2)  # Rate limiting

    set_cached(CACHE_NAME, cache_key, results)
    return results


def _get_place_details(place_id, api_key):
    """Fetch phone number and website from Place Details API."""
    params = {
        "place_id": place_id,
        "fields": "formatted_address,formatted_phone_number,website",
        "key": api_key,
    }
    resp = requests.get(PLACE_DETAILS_URL, params=params)
    data = resp.json()

    if data.get("status") == "OK":
        return data.get("result", {})
    return {}
