"""Look up property owner and zoning info via SerpAPI + Haiku."""

import os
import re
import requests
import anthropic
from utils.cache import get_cached, set_cached

SERPAPI_URL = "https://serpapi.com/search"
CACHE_NAME = "property"


def lookup_property(address, api_key=None):
    """
    Search for property owner/LLC and zoning info for an address.
    Returns dict with property_owner, zoning, property_snippets,
    and a management_search link.
    """
    cache_key = address
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        return cached

    from urllib.parse import quote_plus
    from utils.counties import detect_county, get_property_search_url

    result = {
        "property_owner": "",
        "zoning": "",
        "property_snippets": [],
        "management_search": "",
        "loopnet_link": "",
        "assessor_link": "",
    }

    # Always generate direct lookup links regardless of API availability
    parts = [p.strip() for p in address.split(",")]
    street = parts[0] if parts else address
    city = parts[1].strip() if len(parts) > 1 else ""

    # LoopNet link (great for commercial property details)
    loopnet_query = f'site:loopnet.com "{street}" {city}'
    result["loopnet_link"] = (
        f"https://www.google.com/search?q={quote_plus(loopnet_query)}"
    )

    # County assessor link
    county, assessor_url = get_property_search_url(address)
    if assessor_url:
        result["assessor_link"] = assessor_url

    serpapi_key = api_key or os.environ.get("SERPAPI_KEY", "")
    if not serpapi_key:
        set_cached(CACHE_NAME, cache_key, result)
        return result

    # Search 1: Property owner (uses 2 SerpAPI calls)
    owner_snippets = _search_property_owner(address, serpapi_key)
    result["property_snippets"] = owner_snippets

    # Search 2: Zoning (uses 1 SerpAPI call)
    zoning_snippets = _search_zoning(address, serpapi_key)

    # Use Haiku to extract clean property owner and zoning
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        result["property_owner"] = _extract_property_owner(
            owner_snippets, address, anthropic_key
        )
        result["zoning"] = _extract_zoning(
            zoning_snippets, address, anthropic_key
        )

    # If we found a property owner, search for their management/leasing contacts
    if result["property_owner"] and serpapi_key and anthropic_key:
        owner = result["property_owner"]
        query = f"{owner} property management contact"
        result["management_search"] = (
            f"https://www.google.com/search?q={quote_plus(query)}"
        )
        secondary = _search_secondary_contacts(owner, address, serpapi_key, anthropic_key)
        result["secondary_contacts"] = secondary
    else:
        result["secondary_contacts"] = {}

    set_cached(CACHE_NAME, cache_key, result)
    return result


def _search_property_owner(address, api_key):
    """Search Google for property owner/LLC at this address."""
    parts = [p.strip() for p in address.split(",")]
    street = parts[0] if parts else address
    city = parts[1].strip() if len(parts) > 1 else ""
    state = ""
    if len(parts) > 2:
        state = parts[2].strip().split()[0]  # "GA 30075" -> "GA"

    # Run two searches for better coverage
    queries = [
        # Search 1: Real estate data sites that index owner info
        f'"{street}" {city} {state} site:zillow.com OR site:redfin.com OR site:loopnet.com OR site:propertyshark.com owner',
        # Search 2: County records and general property owner search
        f'"{street}" {city} {state} "property owner" OR "owned by" OR LLC OR "parcel" OR assessor',
    ]

    snippets = []
    for query in queries:
        params = {
            "q": query,
            "api_key": api_key,
            "engine": "google",
            "num": 5,
        }

        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=10)
            data = resp.json()
        except Exception as e:
            snippets.append(f"(Search error: {e})")
            continue

        for r in data.get("organic_results", [])[:3]:
            text_parts = []
            if r.get("title"):
                text_parts.append(r["title"])
            if r.get("snippet"):
                text_parts.append(r["snippet"])
            rich = r.get("rich_snippet", {})
            if rich.get("top", {}).get("detected_extensions", {}):
                text_parts.append(str(rich["top"]["detected_extensions"]))
            source = r.get("displayed_link", "")
            if text_parts:
                snippets.append(f"[{source}] {' — '.join(text_parts)}")

    return snippets if snippets else ["No property owner info found"]


def _search_zoning(address, api_key):
    """Search Google for zoning classification at this address."""
    # Use just the street address for better results
    street = address.split(",")[0].strip()
    city_state = ",".join(address.split(",")[1:3]).strip()

    query = f'zoning "{street}" {city_state} classification OR district OR commercial OR residential'

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": 5,
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        return [f"(Search error: {e})"]

    snippets = []
    for result in data.get("organic_results", [])[:3]:
        snippet = result.get("snippet", "")
        source = result.get("displayed_link", "")
        if snippet:
            snippets.append(f"[{source}] {snippet}")

    return snippets if snippets else ["No zoning info found"]


def _extract_property_owner(snippets, address, api_key):
    """Use Haiku to extract property owner from search snippets."""
    real_snippets = [s for s in snippets if not s.startswith("(") and "No property" not in s]
    if not real_snippets:
        return ""

    snippet_text = "\n".join(real_snippets)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are Google search results about the property at: {address}\n\n"
                    f"{snippet_text}\n\n"
                    f"Who owns this property? I need the property owner — this is usually an LLC, "
                    f"trust, real estate company, or individual who owns the building/land.\n\n"
                    f"Rules:\n"
                    f"- Return ONLY the owner name/entity, nothing else.\n"
                    f"- If it's an LLC or company, return the full entity name.\n"
                    f"- If there's also a property management company, format as: "
                    f"OWNER_NAME (managed by MGMT_COMPANY)\n"
                    f"- If you cannot determine the owner, return exactly: UNKNOWN\n"
                    f"- Your entire response must be just the name or UNKNOWN."
                ),
            }],
        )
        name = message.content[0].text.strip()
        if not name or name == "UNKNOWN" or len(name) > 100:
            return ""
        return name.split("\n")[0].strip()
    except Exception as e:
        print(f"    (Haiku property extraction error: {e})")
        return ""


def _extract_zoning(snippets, address, api_key):
    """Use Haiku to extract zoning classification from search snippets."""
    real_snippets = [s for s in snippets if not s.startswith("(") and "No zoning" not in s]
    if not real_snippets:
        return ""

    snippet_text = "\n".join(real_snippets)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are Google search results about zoning for: {address}\n\n"
                    f"{snippet_text}\n\n"
                    f"What is the zoning classification for this property?\n\n"
                    f"Rules:\n"
                    f"- First line: the zoning code and description, e.g. 'C-1 (Commercial)'\n"
                    f"- Second line: 'Typical uses: ' followed by a brief list of what's "
                    f"typically allowed under this zoning in Georgia municipalities "
                    f"(e.g. retail, restaurants, offices, medical, auto, residential, etc.)\n"
                    f"- Keep it to 2 lines total. No other text.\n"
                    f"- If you cannot determine the zoning, return exactly: UNKNOWN"
                ),
            }],
        )
        zoning = message.content[0].text.strip()
        if not zoning or zoning == "UNKNOWN":
            return ""
        # Keep the full 2-line response (code + typical uses)
        lines = [l.strip() for l in zoning.split("\n") if l.strip()]
        return "\n".join(lines[:2])
    except Exception as e:
        print(f"    (Haiku zoning extraction error: {e})")
        return ""


def _search_secondary_contacts(owner_entity, address, serpapi_key, anthropic_key):
    """
    When we know the property owner (LLC/company), search for their
    management company, leasing agent, or broker contact info.
    Returns dict with mgmt_company, leasing_contact, phone, email.
    """
    result = {
        "mgmt_company": "",
        "leasing_contact": "",
        "phone": "",
        "email": "",
    }

    # Search for the LLC/owner entity + contact info
    query = f'"{owner_entity}" property management OR leasing OR broker contact phone email'

    params = {
        "q": query,
        "api_key": serpapi_key,
        "engine": "google",
        "num": 5,
    }

    try:
        resp = requests.get(SERPAPI_URL, params=params, timeout=10)
        data = resp.json()
    except Exception:
        return result

    snippets = []
    for r in data.get("organic_results", [])[:4]:
        text_parts = []
        if r.get("title"):
            text_parts.append(r["title"])
        if r.get("snippet"):
            text_parts.append(r["snippet"])
        source = r.get("displayed_link", "")
        if text_parts:
            snippets.append(f"[{source}] {' — '.join(text_parts)}")

    if not snippets:
        return result

    snippet_text = "\n".join(snippets)

    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"The property owner is: {owner_entity}\n"
                    f"Property address: {address}\n\n"
                    f"Below are Google search results:\n{snippet_text}\n\n"
                    f"Extract any of the following if available:\n"
                    f"1. Property management company name\n"
                    f"2. Leasing agent or broker name\n"
                    f"3. Phone number\n"
                    f"4. Email address\n\n"
                    f"Return in this exact format (use UNKNOWN for missing fields):\n"
                    f"MGMT: [company name]\n"
                    f"LEASING: [person name]\n"
                    f"PHONE: [number]\n"
                    f"EMAIL: [email]\n"
                    f"No other text."
                ),
            }],
        )
        text = message.content[0].text.strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("MGMT:"):
                val = line[5:].strip()
                if val and val != "UNKNOWN":
                    result["mgmt_company"] = val
            elif line.startswith("LEASING:"):
                val = line[8:].strip()
                if val and val != "UNKNOWN":
                    result["leasing_contact"] = val
            elif line.startswith("PHONE:"):
                val = line[6:].strip()
                if val and val != "UNKNOWN":
                    result["phone"] = val
            elif line.startswith("EMAIL:"):
                val = line[6:].strip()
                if val and val != "UNKNOWN":
                    result["email"] = val
    except Exception as e:
        print(f"    (Secondary contact error: {e})")

    return result
