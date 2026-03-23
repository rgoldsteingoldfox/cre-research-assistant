"""Discover owner/contact info via SerpAPI and website scraping."""

import os
import re
import requests
import anthropic
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
    """Use Claude Haiku to extract owner name from SerpAPI snippets."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    # Skip if no real snippets
    real_snippets = [s for s in snippets if not s.startswith("(") and "No owner info" not in s]
    if not real_snippets:
        return ""

    snippet_text = "\n".join(real_snippets)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    f"Below are Google search snippets about \"{business_name}\".\n\n"
                    f"{snippet_text}\n\n"
                    f"Who is the owner or founder of \"{business_name}\" specifically?\n\n"
                    f"Rules:\n"
                    f"- Return ONLY the name, nothing else. No explanation.\n"
                    f"- If multiple owners, separate with ' & '.\n"
                    f"- Ignore owners of different businesses.\n"
                    f"- If only a first name is available, return just that.\n"
                    f"- If you cannot determine the owner, return exactly: UNKNOWN\n"
                    f"- Your entire response must be just the name or UNKNOWN."
                ),
            }],
        )
        name = message.content[0].text.strip()
        # Reject if UNKNOWN, too long (Haiku got chatty), or empty
        if not name or name == "UNKNOWN" or len(name) > 60:
            return ""
        # If response has multiple lines, just take the first
        name = name.split("\n")[0].strip()
        return name
    except Exception as e:
        print(f"    (Haiku extraction error: {e})")

    return ""


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
