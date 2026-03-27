"""Look up LLC/entity registration and find the person behind it."""

import os
import re
import requests
import anthropic
from utils.cache import get_cached, set_cached

SERPAPI_URL = "https://serpapi.com/search"
CACHE_NAME = "llc"


def lookup_llc(entity_name, state="Georgia", mail_address=""):
    """
    Given an LLC or entity name, find:
    1. Registered agent / principal from Secretary of State (tries multiple states)
    2. Contact info (phone, email, LinkedIn) for that person

    Returns dict with person_name, registered_agent, principal_address,
    phone, email, linkedin, filing_details.
    """
    cache_key = f"{entity_name}|{state}|{mail_address}"
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        return cached

    serpapi_key = os.environ.get("SERPAPI_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

    result = {
        "person_name": "",
        "registered_agent": "",
        "principal_address": "",
        "filing_status": "",
        "phone": "",
        "email": "",
        "linkedin": "",
        "source_snippets": [],
    }

    if not serpapi_key or not anthropic_key:
        return result

    # Build list of states to search — primary state + mailing address state
    states_to_try = [state]
    mail_state = _detect_state_from_address(mail_address)
    if mail_state and mail_state != state:
        states_to_try.append(mail_state)

    # === Step 1: Search for the LLC registration across states ===
    reg_snippets = []
    for try_state in states_to_try:
        print(f"    Searching {try_state} SOS for {entity_name}...")
        snippets = _search_llc_registration(entity_name, try_state, serpapi_key)
        # Check if we got real results (not just "No LLC registration info found")
        real = [s for s in snippets if "No LLC" not in s]
        if real:
            reg_snippets = snippets
            break
        reg_snippets = snippets

    result["source_snippets"] = reg_snippets

    # Extract registration details via Haiku
    reg_details = _extract_registration(reg_snippets, entity_name, anthropic_key)
    result["registered_agent"] = reg_details.get("registered_agent", "")
    result["principal_address"] = reg_details.get("principal_address", "")
    result["filing_status"] = reg_details.get("filing_status", "")

    # The person to look up is the registered agent (or principal)
    person_name = result["registered_agent"]
    if not person_name:
        # Try a broader search for who's behind this entity
        person_name = _search_entity_principal(entity_name, serpapi_key, anthropic_key)

    result["person_name"] = person_name

    # === Step 2: Find contact info for the person ===
    if person_name:
        print(f"    Looking up contact info for {person_name}...")
        contact = _search_person_contact(person_name, entity_name, serpapi_key, anthropic_key)
        result["phone"] = contact.get("phone", "")
        result["email"] = contact.get("email", "")
        result["linkedin"] = contact.get("linkedin", "")

    set_cached(CACHE_NAME, cache_key, result)
    return result


def _detect_state_from_address(address):
    """Extract state from a mailing address like '1345 CHARLOTTESVILLE BLVD, KNOXVILLE TN 37922'."""
    if not address:
        return ""
    STATE_ABBREVS = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming",
    }
    # Look for 2-letter state abbreviation followed by zip code or end of string
    match = re.search(r'\b([A-Z]{2})\s+\d{5}', address.upper())
    if match:
        abbrev = match.group(1)
        return STATE_ABBREVS.get(abbrev, "")
    # Try without zip
    for abbrev, full in STATE_ABBREVS.items():
        if f" {abbrev} " in address.upper() or address.upper().endswith(f" {abbrev}"):
            return full
    return ""


def _search_llc_registration(entity_name, state, api_key):
    """Search for LLC/entity registration details via SerpAPI."""
    queries = [
        f'"{entity_name}" {state} secretary of state registered agent',
        f'"{entity_name}" {state} LLC filing OR registration OR "principal office"',
    ]
    # Add state-specific SOS site search if we know the domain
    sos_sites = {
        "Georgia": "site:ecorp.sos.ga.gov",
        "Tennessee": "site:sos.tn.gov",
        "Florida": "site:search.sunbiz.org",
        "Texas": "site:mycpa.cpa.state.tx.us",
        "North Carolina": "site:sosnc.gov",
        "South Carolina": "site:sos.sc.gov",
        "Alabama": "site:sos.alabama.gov",
        "Ohio": "site:businesssearch.ohiosos.gov",
        "Michigan": "site:cofs.lara.state.mi.us",
        "Indiana": "site:inbiz.in.gov",
        "Illinois": "site:ilsos.gov",
        "Kentucky": "site:sos.ky.gov",
        "Minnesota": "site:sos.state.mn.us",
        "Wisconsin": "site:apps.sos.wi.gov",
        "Iowa": "site:sos.iowa.gov",
    }
    if state in sos_sites:
        queries.append(f'{sos_sites[state]} "{entity_name}"')

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
        except Exception:
            continue

        for r in data.get("organic_results", [])[:3]:
            text_parts = []
            if r.get("title"):
                text_parts.append(r["title"])
            if r.get("snippet"):
                text_parts.append(r["snippet"])
            source = r.get("displayed_link", "")
            if text_parts:
                snippets.append(f"[{source}] {' — '.join(text_parts)}")

    return snippets if snippets else ["No LLC registration info found"]


def _extract_registration(snippets, entity_name, api_key):
    """Use Haiku to extract registered agent and principal from search snippets."""
    real_snippets = [s for s in snippets if not s.startswith("(") and "No LLC" not in s]
    if not real_snippets:
        return {}

    snippet_text = "\n".join(real_snippets)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are Google search results about the entity \"{entity_name}\" "
                    f"registered in Georgia.\n\n"
                    f"{snippet_text}\n\n"
                    f"Extract any of the following if available:\n"
                    f"1. Registered agent name (the person or company listed as agent)\n"
                    f"2. Principal office address\n"
                    f"3. Filing status (active, dissolved, etc.)\n\n"
                    f"Return in this exact format (use UNKNOWN for missing):\n"
                    f"AGENT: [name]\n"
                    f"ADDRESS: [address]\n"
                    f"STATUS: [status]\n"
                    f"No other text."
                ),
            }],
        )
        text = message.content[0].text.strip()
        result = {}
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("AGENT:"):
                val = line[6:].strip()
                if val and val != "UNKNOWN":
                    result["registered_agent"] = val
            elif line.startswith("ADDRESS:"):
                val = line[8:].strip()
                if val and val != "UNKNOWN":
                    result["principal_address"] = val
            elif line.startswith("STATUS:"):
                val = line[7:].strip()
                if val and val != "UNKNOWN":
                    result["filing_status"] = val
        return result
    except Exception:
        return {}


def _search_entity_principal(entity_name, serpapi_key, anthropic_key):
    """Broader search for who owns/controls an entity."""
    query = f'"{entity_name}" owner OR principal OR member OR manager OR "managed by"'

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
        return ""

    snippets = []
    for r in data.get("organic_results", [])[:4]:
        if r.get("snippet"):
            source = r.get("displayed_link", "")
            snippets.append(f"[{source}] {r['snippet']}")

    if not snippets:
        return ""

    snippet_text = "\n".join(snippets)

    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are search results about \"{entity_name}\".\n\n"
                    f"{snippet_text}\n\n"
                    f"Who is the owner, principal, or manager of \"{entity_name}\"?\n"
                    f"Return ONLY the person's name. If unknown, return UNKNOWN."
                ),
            }],
        )
        name = message.content[0].text.strip().split("\n")[0]
        if name and name != "UNKNOWN" and len(name) < 60:
            return name
    except Exception:
        pass

    return ""


def _search_person_contact(person_name, entity_name, serpapi_key, anthropic_key):
    """Search for a person's phone, email, and LinkedIn."""
    result = {"phone": "", "email": "", "linkedin": ""}

    queries = [
        f'"{person_name}" phone OR email OR contact "{entity_name}"',
        f'"{person_name}" site:linkedin.com',
    ]

    all_snippets = []
    linkedin_url = ""

    for query in queries:
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
            continue

        for r in data.get("organic_results", [])[:3]:
            link = r.get("link", "")
            snippet = r.get("snippet", "")
            title = r.get("title", "")
            source = r.get("displayed_link", "")

            # Capture LinkedIn URL
            if "linkedin.com/in/" in link and not linkedin_url:
                linkedin_url = link

            if snippet:
                all_snippets.append(f"[{source}] {title} — {snippet}")

    result["linkedin"] = linkedin_url

    if not all_snippets:
        return result

    snippet_text = "\n".join(all_snippets)

    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are search results about {person_name} "
                    f"(associated with {entity_name}).\n\n"
                    f"{snippet_text}\n\n"
                    f"Extract if available:\n"
                    f"1. Phone number\n"
                    f"2. Email address\n\n"
                    f"Return in this exact format (UNKNOWN for missing):\n"
                    f"PHONE: [number]\n"
                    f"EMAIL: [email]\n"
                    f"No other text."
                ),
            }],
        )
        text = message.content[0].text.strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("PHONE:"):
                val = line[6:].strip()
                if val and val != "UNKNOWN":
                    result["phone"] = val
            elif line.startswith("EMAIL:"):
                val = line[6:].strip()
                if val and val != "UNKNOWN":
                    result["email"] = val
    except Exception:
        pass

    return result
