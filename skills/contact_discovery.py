"""Discover owner/contact info via SerpAPI and website scraping."""

import os
import re
import requests
from bs4 import BeautifulSoup
from utils.cache import get_cached, set_cached

SERPAPI_URL = "https://serpapi.com/search"
CACHE_NAME = "contacts"


def research_business(business_name, city, website=None, api_key=None):
    """
    Attempt to find owner/contact info for a business.
    1. SerpAPI search for owner/founder
    2. If website exists, scrape for emails, phones, names
    Returns dict with owner_snippets, emails, phones, names.
    """
    cache_key = f"{business_name}|{city}"
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        return cached

    result = {
        "owner_snippets": [],
        "emails": [],
        "phones": [],
        "names": [],
    }

    # 1. SerpAPI owner search
    snippets = _search_owner(business_name, city, api_key)
    result["owner_snippets"] = snippets
    result["owner_name"] = _extract_owner_from_snippets(snippets, business_name)

    # 2. Website scraping
    if website:
        scraped = _scrape_website(website)
        result["emails"] = scraped.get("emails", [])
        result["phones"] = scraped.get("phones", [])
        result["names"] = scraped.get("names", [])

        # If we didn't get an owner from SerpAPI, try website names
        if not result["owner_name"] and result["names"]:
            result["owner_name"] = result["names"][0]

    set_cached(CACHE_NAME, cache_key, result)
    return result


def _extract_owner_from_snippets(snippets, business_name):
    """Extract a clean owner/founder name from SerpAPI snippet text."""
    biz_lower = business_name.lower()
    candidates = []

    for snippet in snippets:
        # Skip error/empty snippets
        if snippet.startswith("(") or "No owner info" in snippet:
            continue

        patterns = [
            # "owner Sabrina Kaylor" or "owner, John Smith" or "owner @Name"
            r'[Oo]wner[,:]?\s+(?:@)?([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+)',
            # "founder Jonathan D. Golden"
            r'[Ff]ounder[,:]?\s+(?:@)?([A-Z][a-z]+(?:\s+[A-Z]\.?\s*[A-Z]?[a-z\']*)+)',
            # "owned and operated by a sole business owner named Hassane"
            r'owner\s+named\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)*)',
            # "owned by John Smith" or "owned and operated by..."
            r'[Oo]wned\s+(?:and operated\s+)?by\s+(?:@)?([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*(?:\s+[A-Z][a-z\']+)*)',
            # "founded by John Smith"
            r'[Ff]ounded\s+by\s+(?:@)?([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*(?:\s+[A-Z][a-z\']+)*)',
            # "co-owner John Smith" or "co-owner, John Smith"
            r'[Cc]o-?owner[,:]?\s+(?:@)?([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+)',
            # "Chef-owner John Smith"
            r'[Cc]hef[/-][Oo]wner\s+(?:@)?([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+)',
            # "Meet Colin, the co-owner" or "Meet our owner, Gordy"
            r'[Mm]eet\s+(?:our\s+)?(?:owner,?\s+)?(?:@)?([A-Z][a-z]+)',
            # "John Smith, owner" or "John Smith, founder"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+),?\s+(?:the\s+)?(?:owner|founder|co-owner|proprietor)',
            # Knowledge Graph format: "Owner: John Smith"
            r'(?:Owner|Founder):\s+([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)*)',
            # "Tony is the owner"
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)*)\s+is\s+the\s+(?:owner|founder|co-owner)',
        ]

        for pat in patterns:
            for match in re.finditer(pat, snippet):
                name = match.group(1).strip().rstrip('.,;:')
                name = _clean_owner_name(name, biz_lower)
                if name:
                    candidates.append(name)

    # Prefer names with first + last over single names
    full_names = [n for n in candidates if ' ' in n]
    if full_names:
        return full_names[0]
    if candidates:
        return candidates[0]
    return ""


def _clean_owner_name(name, biz_lower):
    """Validate and clean an extracted owner name. Returns empty string if invalid."""
    # Strip leading title words that aren't part of the name
    strip_prefixes = [
        'Veteran Stuntwoman ', 'Chef ', 'Dr ', 'Mr ', 'Mrs ', 'Ms ',
        'Part ', 'General ', 'Our ',
    ]
    for prefix in strip_prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]

    name = name.strip().rstrip('.,;:')

    # Reject if empty or too short/long
    if not name or len(name) < 2 or len(name) > 40:
        return ""

    # Reject generic/bad words as the entire name or first word
    bad_words = {
        'the', 'our', 'their', 'this', 'coffee', 'cafe', 'shop', 'house',
        'roaster', 'bakery', 'restaurant', 'meet', 'crush', 'big', 'oak',
        'tavern', 'brewing', 'brewery', 'provisions', 'kitchen', 'market',
    }
    first_word = name.split()[0].lower()
    if first_word in bad_words:
        return ""
    if name.lower() in bad_words:
        return ""

    # Reject if name is part of a different business (contains "'s" + business word)
    if "'s " in name and any(w in name.lower() for w in ['tavern', 'bar', 'grill', 'cafe', 'coffee', 'shop']):
        return ""

    # Reject if it's the business name itself
    if name.lower() in biz_lower:
        return ""

    return name


def _search_owner(business_name, city, api_key=None):
    """Search SerpAPI for owner/founder info. Returns top snippet strings."""
    api_key = api_key or os.environ.get("SERPAPI_KEY", "")
    if not api_key:
        return ["(No SerpAPI key — skipping web search)"]

    query = f'"{business_name}" {city} owner OR founder OR "owned by"'

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

    # Check knowledge graph first
    kg = data.get("knowledge_graph", {})
    if kg:
        # Sometimes Google knows the owner directly
        for attr in kg.get("attributes", []):
            if "owner" in attr.get("name", "").lower() or "founder" in attr.get("name", "").lower():
                snippets.append(f"[Knowledge Graph] {attr['name']}: {attr['value']}")

    # Check organic results for snippets
    for result in data.get("organic_results", [])[:3]:
        snippet = result.get("snippet", "")
        title = result.get("title", "")
        source = result.get("displayed_link", "")
        if snippet:
            snippets.append(f"[{source}] {snippet}")

    return snippets if snippets else ["No owner info found in search results"]


def _scrape_website(url):
    """Scrape a business website for contact info. Best-effort only."""
    result = {"emails": [], "phones": [], "names": []}

    # Try homepage and common contact/about pages
    pages_to_try = [url]
    base = url.rstrip("/")
    for path in ["/about", "/about-us", "/contact", "/our-story", "/our-team"]:
        pages_to_try.append(base + path)

    seen_emails = set()
    seen_phones = set()
    seen_names = set()

    for page_url in pages_to_try:
        try:
            resp = requests.get(page_url, timeout=8, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36"
            })
            if resp.status_code != 200:
                continue

            html = resp.text
            soup = BeautifulSoup(html, "html.parser")
            text = soup.get_text(separator=" ", strip=True)

            # Extract emails
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            for e in emails:
                e_lower = e.lower()
                # Filter out common non-contact emails
                if not any(skip in e_lower for skip in [
                    "sentry", "webpack", "example", "wixpress", "sentry.io",
                    ".png", ".jpg", ".svg", "noreply", "no-reply"
                ]):
                    if e_lower not in seen_emails:
                        seen_emails.add(e_lower)
                        result["emails"].append(e)

            # Extract phone numbers (US format)
            phones = re.findall(
                r'(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
                text
            )
            for p in phones:
                digits = re.sub(r'\D', '', p)
                if len(digits) >= 10 and digits not in seen_phones:
                    seen_phones.add(digits)
                    result["phones"].append(p.strip())

            # Extract owner/founder names
            owner_patterns = [
                r'(?:owned|founded|started)\s+by\s+([A-Z][a-z]+(?:\s+(?:and|&)\s+[A-Z][a-z]+)*(?:\s+[A-Z][a-z\']+)*)',
                r'(?:Owner|Founder|Proprietor|CEO)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+)',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z\']+)+),?\s+(?:Owner|Founder|Proprietor|CEO)',
            ]
            for pat in owner_patterns:
                matches = re.findall(pat, text)
                for m in matches:
                    name = m.strip().rstrip('.,;')
                    if 3 < len(name) < 40 and name not in seen_names:
                        seen_names.add(name)
                        result["names"].append(name)

        except Exception:
            continue

    return result
