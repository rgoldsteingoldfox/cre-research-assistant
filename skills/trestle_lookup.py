"""Reverse address lookup via Trestle API — find residents at a property address."""

import os
import requests
from utils.cache import get_cached, set_cached

TRESTLE_URL = "https://api.trestleiq.com/3.1/location"
CACHE_NAME = "trestle"


def trestle_lookup(street, city, state, zip_code):
    """
    Look up current residents at an address via Trestle reverse address API.

    Returns list of dicts with name, phones, emails.
    """
    api_key = os.environ.get("TRESTLE_API_KEY", "")
    if not api_key:
        print("    Trestle: No TRESTLE_API_KEY set, skipping.")
        return []

    cache_key = f"{street}|{city}|{state}|{zip_code}"
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        return cached

    print(f"    Trestle: Looking up {street}, {city}, {state} {zip_code}...")

    try:
        resp = requests.get(TRESTLE_URL, params={
            "street_line_1": street,
            "city": city,
            "state_code": state,
            "postal_code": zip_code,
        }, headers={
            "x-api-key": api_key,
            "accept": "application/json",
        }, timeout=15)

        if resp.status_code != 200:
            print(f"    Trestle: API error {resp.status_code}: {resp.text[:200]}")
            return []

        data = resp.json()
        residents = data.get("current_residents", [])

        if not residents:
            print("    Trestle: No residents found.")
            set_cached(CACHE_NAME, cache_key, [])
            return []

        results = []
        for r in residents:
            phones = []
            for p in (r.get("phones") or []):
                phones.append({
                    "number": p.get("phone_number", ""),
                    "type": p.get("line_type", "unknown"),
                })

            results.append({
                "name": r.get("name", ""),
                "phones": phones,
                "emails": [e for e in (r.get("emails") or []) if e],
            })

        print(f"    Trestle: Found {len(results)} resident(s).")
        set_cached(CACHE_NAME, cache_key, results)
        return results

    except Exception as e:
        print(f"    Trestle: Request failed — {e}")
        return []
