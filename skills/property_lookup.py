"""Look up property owner and zoning info via city ArcGIS APIs + SerpAPI fallback."""

import os
import re
import requests
import anthropic
from utils.cache import get_cached, set_cached

SERPAPI_URL = "https://serpapi.com/search"
CACHE_NAME = "property"

# City ArcGIS FeatureServer endpoints with layer IDs and field mappings
# Each entry: (base_url, layer_id, {field_map})
ARCGIS_ENDPOINTS = {
    "Roswell": {
        "url": "https://gisweb.ci.roswell.ga.us/arcgis/rest/services/ArcGISHub/ArcGIS_Hub_REST_Services/FeatureServer",
        "layer": 4,
        "fields": {
            "address": "SITEADDRES",
            "zoning_code": "USECD",
            "zoning_desc": "USEDSCRP",
            "owner": "OWNERNME1",
            "owner2": "OWNERNME2",
            "parcel_id": "PARCELID",
        },
    },
    "Alpharetta": {
        "url": "https://alphagis.alpharetta.ga.us/arcgis/rest/services/TaxParcels/FeatureServer",
        "layer": 0,
        "fields": {
            "address": "Address",
            "zoning_code": "ClassCode",
            "zoning_desc": "",  # No description field — just the code
            "owner": "Owner",
            "owner2": "",
            "parcel_id": "ParcelID",
            "mail_addr1": "OwnerAddr1",
            "mail_addr2": "OwnerAddr2",
        },
    },
}

# County-level ArcGIS endpoints — cover ALL cities in the county
# These use MapServer (not FeatureServer) but query the same way
COUNTY_ARCGIS_ENDPOINTS = {
    "Fulton": {
        "url": "https://gismaps.fultoncountyga.gov/arcgispub2/rest/services/PropertyMapViewer/PropertyMapViewer/MapServer",
        "layer": 11,
        "fields": {
            "address": "Address",
            "zoning_code": "ClassCode",
            "zoning_desc": "",
            "owner": "Owner",
            "owner2": "",
            "parcel_id": "ParcelID",
            "mail_addr1": "OwnerAddr1",
            "mail_addr2": "OwnerAddr2",
        },
        "cities": [
            "Sandy Springs", "Johns Creek", "Milton", "Atlanta",
            "East Point", "College Park", "Union City", "Fairburn",
            "Palmetto", "Hapeville", "Chattahoochee Hills", "Mountain Park",
        ],
    },
    "Cobb": {
        "url": "https://services.arcgis.com/seTexOicoRXDvRsJ/arcgis/rest/services/Parcels_Enriched/FeatureServer",
        "layer": 0,
        "fields": {
            "address": "LOCATION_ADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNER_NAME",
            "owner2": "",
            "parcel_id": "STATE_PARCEL_NO",
            "mail_addr1": "MAILING_ADDRESS_LINE_1",
            "mail_addr2": "MAILING_CITY_NAME",
        },
        "cities": [
            "Marietta", "Smyrna", "Kennesaw", "Acworth",
            "Powder Springs", "Austell", "Mableton",
        ],
    },
    "Gwinnett": {
        "url": "https://services3.arcgis.com/RfpmnkSAQleRbndX/arcgis/rest/services/Property_and_Tax/FeatureServer",
        "layer": 0,
        "fields": {
            "address": "ADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "USERNAME",
            "owner2": "",
            "parcel_id": "PIN",
        },
        "cities": [
            "Duluth", "Lawrenceville", "Suwanee", "Norcross",
            "Peachtree Corners", "Lilburn", "Snellville",
            "Buford", "Dacula", "Grayson", "Loganville",
        ],
    },
    "DeKalb": {
        "url": "https://dcgis.dekalbcountyga.gov/hosted/rest/services/Parcels/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "ZONING",
            "zoning_desc": "CLASSDSCRP",
            "owner": "OWNERNME1",
            "owner2": "OWNERNME2",
            "parcel_id": "PARCELID",
            "mail_addr1": "PSTLADDRESS",
            "mail_addr2": "PSTLCITYSTATEZIP",
        },
        "cities": [
            "Dunwoody", "Brookhaven", "Decatur", "Tucker",
            "Stonecrest", "Chamblee", "Doraville", "Clarkston",
            "Avondale Estates", "Pine Lake", "Lithonia",
        ],
    },
    "Cherokee": {
        "url": "https://gis.cherokeecountyga.gov/arcgis/rest/services/MainLayersPRO/MapServer",
        "layer": 1,
        "fields": {
            "address": "Property_Address",
            "zoning_code": "Zoning",
            "zoning_desc": "",
            "owner": "OWNER",
            "owner2": "",
            "parcel_id": "PIN",
            "mail_addr1": "Mailing_Address",
            "mail_addr2": "Mailing_City",
        },
        "cities": [
            "Woodstock", "Canton", "Holly Springs", "Ball Ground",
            "Waleska",
        ],
    },
    "Forsyth": {
        "url": "https://geo.forsythco.com/gis/rest/services/EnerGov/EnerGovParcelAddressMapService/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "OWNERNME2",
            "parcel_id": "PARCELID",
            "mail_addr1": "PSTLADDRESS",
            "mail_addr2": "PSTLCITY",
        },
        "cities": [
            "Cumming", "Sugar Hill",
        ],
    },
    "Henry": {
        "url": "https://arcgis.co.henry.ga.us/server/rest/services/Parcels/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "OWNERNME2",
            "parcel_id": "PARCELID",
            "mail_addr1": "PSTLADDRESS",
            "mail_addr2": "PSTLCITY",
        },
        "cities": [
            "McDonough", "Stockbridge", "Hampton", "Locust Grove",
        ],
    },
    "Douglas": {
        "url": "https://gis.dcga.us/arcgis/rest/services/MapLayers/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
            "mail_addr1": "PSTLADDRESS",
            "mail_addr2": "PSTLCITY",
        },
        "cities": [
            "Douglasville",
        ],
    },
    "Hall": {
        "url": "https://webmap.hallcounty.org/server/rest/services/GHCGIS_WebData/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Gainesville", "Flowery Branch", "Oakwood",
        ],
    },
    "Fayette": {
        "url": "https://gis.peachtree-city.org/arcgis/rest/services/Peachtree_City_Parcels/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Fayetteville", "Peachtree City", "Tyrone",
        ],
    },
    "Coweta": {
        "url": "https://coweta-gis-web.coweta.ga.us/arcgis/rest/services/Parcels/FeatureServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Newnan", "Senoia", "Sharpsburg",
        ],
    },
    "Jackson": {
        "url": "https://jcgis.jacksongov.org/arcgis/rest/services/ParcelViewer/CityAndDistrict_Layers/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Jefferson", "Hoschton", "Braselton",
        ],
    },
    "Walton": {
        "url": "https://services1.arcgis.com/TaXHPwWfIMuzJ7Ov/arcgis/rest/services/WaltonCountyPropeties/FeatureServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Monroe", "Loganville", "Social Circle",
        ],
    },
    "Chatham": {
        "url": "https://pub.sagis.org/arcgis/rest/services/Pictometry/ParcelDigest/MapServer",
        "layer": 0,
        "fields": {
            "address": "SITEADDRESS",
            "zoning_code": "",
            "zoning_desc": "",
            "owner": "OWNERNME1",
            "owner2": "",
            "parcel_id": "PARCELID",
        },
        "cities": [
            "Savannah", "Pooler", "Garden City", "Tybee Island",
        ],
    },
}


def lookup_property(address, api_key=None):
    """
    Look up property owner and zoning for an address.
    Strategy: Try city ArcGIS API first (free, accurate), fall back to SerpAPI.
    """
    cache_key = address
    cached = get_cached(CACHE_NAME, cache_key)
    if cached:
        return cached

    from urllib.parse import quote_plus
    from utils.counties import detect_county, get_property_search_url, get_qpublic_url, get_ga_sos_url, get_gsccca_url

    result = {
        "property_owner": "",
        "zoning": "",
        "zoning_uses": "",
        "parcel_id": "",
        "data_source": "",
        "property_snippets": [],
        "management_search": "",
        "loopnet_link": "",
        "assessor_link": "",
        "secondary_contacts": {},
    }

    # Parse address
    parts = [p.strip() for p in address.split(",")]
    street = parts[0] if parts else address
    city = parts[1].strip() if len(parts) > 1 else ""

    # Generate lookup links
    loopnet_query = f'site:loopnet.com "{street}" {city}'
    result["loopnet_link"] = f"https://www.google.com/search?q={quote_plus(loopnet_query)}"
    county, assessor_url = get_property_search_url(address)
    if assessor_url:
        result["assessor_link"] = assessor_url

    # Direct lookup links
    qpublic_url = get_qpublic_url(address)
    if qpublic_url:
        result["qpublic_link"] = qpublic_url
    result["ga_sos_link"] = get_ga_sos_url()
    result["gsccca_link"] = get_gsccca_url()

    # === Strategy 1: Try ArcGIS direct lookup (free, instant, accurate) ===
    arcgis_result = _query_arcgis(street, city)
    if arcgis_result:
        result["property_owner"] = arcgis_result.get("owner", "")
        result["zoning"] = arcgis_result.get("zoning", "")
        result["parcel_id"] = arcgis_result.get("parcel_id", "")
        result["owner_mail_address"] = arcgis_result.get("owner_mail_address", "")
        result["data_source"] = arcgis_result.get("source", "ArcGIS")

        # Use Haiku to interpret what the zoning allows
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if result["zoning"] and anthropic_key:
            result["zoning_uses"] = _interpret_zoning(result["zoning"], city, anthropic_key)

    # === Strategy 2: Fall back to SerpAPI if ArcGIS didn't find it ===
    if not result["property_owner"] and not result["zoning"]:
        serpapi_key = api_key or os.environ.get("SERPAPI_KEY", "")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")

        if serpapi_key:
            owner_snippets = _search_property_owner(address, serpapi_key)
            result["property_snippets"] = owner_snippets
            zoning_snippets = _search_zoning(address, serpapi_key)

            if anthropic_key:
                result["property_owner"] = _extract_property_owner(
                    owner_snippets, address, anthropic_key
                )
                zoning_full = _extract_zoning(zoning_snippets, address, anthropic_key)
                if zoning_full:
                    lines = zoning_full.split("\n")
                    result["zoning"] = lines[0]
                    if len(lines) > 1:
                        result["zoning_uses"] = lines[1]

            result["data_source"] = "SerpAPI"

    # === Search for management/leasing contacts if we found a property owner ===
    if result["property_owner"]:
        owner = result["property_owner"]
        query = f"{owner} property management contact"
        result["management_search"] = f"https://www.google.com/search?q={quote_plus(query)}"

        serpapi_key = api_key or os.environ.get("SERPAPI_KEY", "")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if serpapi_key and anthropic_key:
            result["secondary_contacts"] = _search_secondary_contacts(
                owner, address, serpapi_key, anthropic_key
            )

        # === LLC lookup: find the person behind the entity ===
        # Trigger if owner looks like an LLC/Corp/Trust/entity (not an individual name)
        if _looks_like_entity(owner):
            from skills.llc_lookup import lookup_llc
            print(f"  Looking up LLC: {owner}...")
            llc_data = lookup_llc(owner, mail_address=result.get("owner_mail_address", ""))

            # === Mailing address reverse lookup ===
            # If SOS/LLC search didn't find the person, and we have a mailing
            # address, search for who lives there — that's usually the principal.
            mail_addr = result.get("owner_mail_address", "")
            if not llc_data.get("person_name") and mail_addr:
                serpapi_key2 = api_key or os.environ.get("SERPAPI_KEY", "")
                anthropic_key2 = os.environ.get("ANTHROPIC_API_KEY", "")
                if serpapi_key2 and anthropic_key2:
                    print(f"  Reverse-looking up mailing address: {mail_addr}...")
                    person = _reverse_lookup_mailing_address(
                        mail_addr, owner, serpapi_key2, anthropic_key2
                    )
                    if person.get("person_name"):
                        llc_data["person_name"] = person["person_name"]
                    if person.get("background"):
                        llc_data["background"] = person["background"]
                    if person.get("principal_address") and not llc_data.get("principal_address"):
                        llc_data["principal_address"] = mail_addr

            # === Manual enrichment override ===
            # Check data/enrichments.json for manually researched data
            enrichment = _get_enrichment(address)
            if enrichment:
                llc_override = enrichment.get("llc_override", {})
                if llc_override.get("person_name"):
                    llc_data["person_name"] = llc_override["person_name"]
                if llc_override.get("background"):
                    llc_data["background"] = llc_override["background"]
                if llc_override.get("principal_address"):
                    llc_data["principal_address"] = llc_override["principal_address"]
                if llc_override.get("source"):
                    llc_data["enrichment_source"] = llc_override["source"]

            result["llc_details"] = llc_data

    set_cached(CACHE_NAME, cache_key, result)
    return result


def _query_arcgis(street, city):
    """Query city or county ArcGIS for property/zoning data."""
    # Normalize city name
    city_clean = city.strip().title()

    # Try city-specific endpoint first
    config = ARCGIS_ENDPOINTS.get(city_clean)

    # If no city endpoint, try county-level endpoints
    if not config:
        for county_name, county_config in COUNTY_ARCGIS_ENDPOINTS.items():
            if city_clean in county_config.get("cities", []):
                config = county_config
                break

    if not config:
        return None
    url = f"{config['url']}/{config['layer']}/query"
    fields = config["fields"]

    # Build address search — use LIKE for fuzzy matching
    # Strip suite numbers and normalize common abbreviations
    search_addr = street.split(" Suite")[0].split(" Ste")[0].split(" #")[0].strip()

    # Use just the street number for matching — handles all variations
    # "7900 Northpoint Parkway" and "7900 North Point Pkwy" both start with "7900"
    # The LIKE query with just the number is broad enough to find the right record
    import re as _re
    number_match = _re.match(r'^(\d+)', search_addr)
    if number_match:
        street_num = number_match.group(1)
        # Use number + first word of street name for tighter match
        words = search_addr.split()
        if len(words) >= 2:
            # Use number + beginning of second word (handles "Northpoint" vs "North")
            second_word = words[1][:5]  # First 5 chars of street name
            search_addr = f"{street_num} {second_word}"

    # Uppercase for case-insensitive matching (some counties store UPPERCASE)
    search_addr_upper = search_addr.upper()

    params = {
        "where": f"{fields['address']} LIKE '{search_addr_upper}%'",
        "outFields": ",".join(v for v in fields.values() if v),
        "f": "json",
        "resultRecordCount": 1,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
    except Exception:
        return None

    features = data.get("features", [])
    if not features:
        return None

    attrs = features[0].get("attributes", {})

    owner = (attrs.get(fields["owner"], "") or "").strip()
    owner2 = (attrs.get(fields.get("owner2", ""), "") or "").strip()
    if owner2:
        owner = f"{owner} / {owner2}"

    zoning_code = (attrs.get(fields["zoning_code"], "") or "").strip()
    zoning_desc = (attrs.get(fields.get("zoning_desc", ""), "") or "").strip()
    zoning = f"{zoning_code} - {zoning_desc}" if zoning_desc else zoning_code

    parcel_id = (attrs.get(fields.get("parcel_id", ""), "") or "").strip()

    # Owner mailing address (where tax bills go — often the owner's actual address)
    mail_addr1 = (attrs.get(fields.get("mail_addr1", ""), "") or "").strip()
    mail_addr2 = (attrs.get(fields.get("mail_addr2", ""), "") or "").strip()
    mail_address = ", ".join(p for p in [mail_addr1, mail_addr2] if p)

    return {
        "owner": owner,
        "zoning": zoning,
        "parcel_id": parcel_id,
        "owner_mail_address": mail_address,
        "source": f"ArcGIS ({city_clean})",
    }


def _interpret_zoning(zoning, city, api_key):
    """Use Haiku to explain what a zoning classification typically allows."""
    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{
                "role": "user",
                "content": (
                    f"Zoning code: {zoning}\n"
                    f"City: {city}, Georgia\n\n"
                    f"Based on the zoning CODE LETTER (C=Commercial, R=Residential, "
                    f"M=Mixed, I=Industrial, O=Office, etc.) and common Georgia municipal "
                    f"zoning standards, what uses are typically allowed?\n"
                    f"Return ONE line: 'Typical uses: ' followed by a comma-separated list.\n"
                    f"If unsure of the specific code, interpret the letter prefix.\n"
                    f"No other text. No disclaimers. Just the one line."
                ),
            }],
        )
        text = message.content[0].text.strip()
        return text.split("\n")[0]
    except Exception:
        return ""


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


def _get_enrichment(address):
    """Check data/enrichments.json for manually researched data for this address."""
    import json
    enrichments_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "enrichments.json")
    if not os.path.exists(enrichments_path):
        return None
    try:
        with open(enrichments_path, "r") as f:
            data = json.load(f)
        # Try exact match first
        if address in data:
            return data[address]
        # Fuzzy: match on street number + city
        # "7900 Northpoint Parkway, Alpharetta" matches "7900 North Point Pkwy, Alpharetta"
        addr_num = re.match(r'^(\d+)', address.split(",")[0].strip())
        addr_city = address.split(",")[1].strip().upper() if "," in address else ""
        if addr_num:
            for key, val in data.items():
                key_num = re.match(r'^(\d+)', key.split(",")[0].strip())
                key_city = key.split(",")[1].strip().upper() if "," in key else ""
                if key_num and addr_num.group(1) == key_num.group(1) and addr_city == key_city:
                    return val
        return None
    except Exception:
        return None


def _reverse_lookup_mailing_address(mail_address, entity_name, serpapi_key, anthropic_key):
    """
    When an LLC's SOS lookup fails, search for who lives at the tax mailing
    address. Private investors usually mail taxes to their home — the resident
    at that address is almost always the LLC principal.
    """
    result = {"person_name": "", "background": ""}

    # Parse street from mailing address
    parts = [p.strip() for p in mail_address.split(",")]
    street = parts[0] if parts else mail_address

    queries = [
        f'"{street}" property owner OR resident OR homeowner',
        f'"{street}" "{parts[1].strip()}" owner' if len(parts) > 1 else f'"{street}" owner',
    ]

    all_snippets = []
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

        for r in data.get("organic_results", [])[:4]:
            text_parts = []
            if r.get("title"):
                text_parts.append(r["title"])
            if r.get("snippet"):
                text_parts.append(r["snippet"])
            source = r.get("displayed_link", "")
            if text_parts:
                all_snippets.append(f"[{source}] {' — '.join(text_parts)}")

    if not all_snippets:
        return result

    snippet_text = "\n".join(all_snippets)

    try:
        client = anthropic.Anthropic(api_key=anthropic_key)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            messages=[{
                "role": "user",
                "content": (
                    f"I'm looking for the person who lives at: {mail_address}\n"
                    f"This address receives tax mail for the commercial property entity "
                    f"\"{entity_name}\" — so the resident is likely the LLC principal.\n\n"
                    f"Below are Google search results:\n{snippet_text}\n\n"
                    f"Extract:\n"
                    f"1. Person name(s) who own or live at this residential address\n"
                    f"2. Any background info (family, business ties, other holdings)\n\n"
                    f"Return in this exact format:\n"
                    f"PERSON: [name(s)]\n"
                    f"BACKGROUND: [brief background or UNKNOWN]\n"
                    f"No other text."
                ),
            }],
        )
        text = message.content[0].text.strip()
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("PERSON:"):
                val = line[7:].strip()
                if val and val != "UNKNOWN" and len(val) < 100:
                    result["person_name"] = val
            elif line.startswith("BACKGROUND:"):
                val = line[11:].strip()
                if val and val != "UNKNOWN" and len(val) < 300:
                    result["background"] = val
    except Exception as e:
        print(f"    (Mailing address reverse lookup error: {e})")

    return result


def _looks_like_entity(name):
    """Check if a property owner name looks like an LLC/Corp/Trust rather than a person."""
    if not name:
        return False
    entity_indicators = [
        "LLC", "L.L.C.", "INC", "CORP", "LP", "L.P.", "LTD",
        "TRUST", "PARTNERS", "PARTNERSHIP", "HOLDINGS", "GROUP",
        "PROPERTIES", "REALTY", "INVESTMENTS", "ASSOCIATES",
        "VENTURES", "CAPITAL", "MANAGEMENT", "DEVELOPMENT",
        "ENTERPRISES", "FUND", "FOUNDATION",
    ]
    name_upper = name.upper()
    return any(indicator in name_upper for indicator in entity_indicators)
