"""Generate research links for zoning, property ownership, and owner search."""

from urllib.parse import quote_plus
from utils.counties import (
    detect_county, get_property_search_url, get_qpublic_url,
    get_municode_url, get_ga_sos_url, get_gsccca_url,
)


def generate_links(business_name, address, city=""):
    """
    Generate all research links for a business.
    Returns dict with owner_search, zoning_search, property_search,
    county, county_gis, qpublic, municode, ga_sos, gsccca URLs.
    """
    links = {}
    search_city = city or _extract_city(address)

    # Business owner search
    owner_query = f"owner of {business_name} {search_city}"
    links["owner_search"] = f"https://www.google.com/search?q={quote_plus(owner_query)}"

    # Property owner search
    property_query = f"property owner {address}"
    links["property_search"] = f"https://www.google.com/search?q={quote_plus(property_query)}"

    # Leasing search
    leasing_query = f"leasing {address}"
    links["leasing_search"] = f"https://www.google.com/search?q={quote_plus(leasing_query)}"

    # Property manager search
    pm_query = f"property manager {address}"
    links["property_manager_search"] = f"https://www.google.com/search?q={quote_plus(pm_query)}"

    # Zoning search
    zoning_query = f"zoning {address}"
    links["zoning_search"] = f"https://www.google.com/search?q={quote_plus(zoning_query)}"

    # County-specific GIS link
    county, gis_url = get_property_search_url(address)
    links["county"] = county
    if gis_url:
        links["county_gis"] = gis_url

    # === Direct lookup links ===

    # qPublic — free county property search (owner of record, no login)
    qpublic_url = get_qpublic_url(address)
    if qpublic_url:
        links["qpublic"] = qpublic_url

    # Municode — municipal code / zoning ordinance for the city
    municode_url = get_municode_url(search_city)
    if municode_url:
        links["municode"] = municode_url

    # GA Secretary of State — LLC/entity registration lookup
    links["ga_sos"] = get_ga_sos_url()

    # GSCCCA — deed search (grantor/grantee history)
    links["gsccca"] = get_gsccca_url()

    return links


def _extract_city(address):
    """Pull city name from a formatted address string."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 3:
        return parts[-3]  # Usually: street, city, state zip, country
    elif len(parts) >= 2:
        return parts[-2]
    return ""
