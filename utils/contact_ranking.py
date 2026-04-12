"""Rank and classify contacts from LLC, Trestle, and web sources."""

import re

# Keywords that indicate the registered agent is a filing service, law firm, or company — not a decision-maker
FILING_AGENT_PATTERNS = [
    # Filing / registered agent services
    r'\bregistered\s*agent',
    r'\bcorp\s*service',
    r'\bct\s*corporation',
    r'\bnational\s*registered',
    r'\bincorporating\s*services',
    r'\blegal\s*zoom',
    r'\blegalzoom',
    r'\brocket\s*lawyer',
    r'\bzenbusiness',
    r'\bnorthwest\s*registered',
    r'\bharbor\s*compliance',
    r'\bsunbiz',
    r'\bcsc\s*global',
    r'\bparacorp',
    r'\bvcorp',
    r'\bwolters\s*kluwer',
    r'\bprentice\s*hall',
    r'\bcogency\s*global',
    r'\bunited\s*agent',
    r'\bincfile',
    r'\bbizfilings',
    # Law firms / attorneys
    r'\blaw\s*(firm|office|group|practice)',
    r'\battorney',
    r'\besq\.?\b',
    r'\bllp\b',
    r'\b[a-z]+,?\s*(p\.?a\.?|p\.?c\.?|p\.?l\.?l\.?c\.?)$',
    # Generic company indicators (when the agent IS a company)
    r'\binc\.?\b',
    r'\bcorp(oration)?\.?\b',
    r'\bllc\b',
    r'\bltd\.?\b',
    r'\bservices?\s*(inc|llc|corp)',
    r'\bgroup\b',
    r'\bassociates\b',
    r'\b&\s*associates',
]


def is_filing_agent(name):
    """Check if a registered agent name looks like a filing service, law firm, or company."""
    if not name:
        return False
    name_lower = name.lower().strip()
    for pattern in FILING_AGENT_PATTERNS:
        if re.search(pattern, name_lower):
            return True
    return False


def is_person_name(name):
    """Check if a name looks like an individual person (not a company)."""
    if not name:
        return False
    name_lower = name.lower().strip()
    # Companies tend to have these
    company_signals = [
        'llc', 'inc', 'corp', 'ltd', 'group', 'holdings',
        'properties', 'ventures', 'capital', 'management',
        'services', 'associates', 'partners', 'enterprises',
        'solutions', 'consulting', 'the ', 'foundation',
    ]
    for signal in company_signals:
        if signal in name_lower:
            return False
    # A person name is typically 2-4 words, all starting with uppercase
    words = name.strip().split()
    if len(words) < 2 or len(words) > 5:
        return False
    # Each word in a real name starts with a capital letter followed by lowercase
    # Company names often have all-caps words or unusual patterns
    for word in words:
        # Allow suffixes like Jr, Sr, III, II, IV
        if word in ("Jr", "Sr", "II", "III", "IV", "V"):
            continue
        # Must start with uppercase, rest mostly lowercase
        if not word[0].isupper():
            return False
        # If it's all uppercase and longer than 2 chars, probably not a person name
        if word.isupper() and len(word) > 2:
            return False
    # Final heuristic: common person name has at least one word that looks like a first name
    # (3+ letters, not all consonants)
    import re
    has_vowel_word = any(re.search(r'[aeiou]', w, re.IGNORECASE) for w in words)
    if not has_vowel_word:
        return False
    return True


def _is_commercial_zoning(zoning):
    """Check if zoning code indicates a commercial/office/industrial property."""
    if not zoning:
        return False
    zoning_upper = zoning.upper().strip()
    # Common commercial zoning prefixes
    commercial_prefixes = [
        "C", "C-", "C1", "C2", "C3", "C4", "C5",
        "O", "O-", "O1", "O2",  # Office
        "M", "M-", "M1", "M2",  # Mixed-use / Industrial
        "I", "I-", "I1", "I2",  # Industrial
        "B", "B-", "B1", "B2",  # Business
        "MU",  # Mixed-use
        "CG", "CL", "CC",  # Commercial general/local/community
    ]
    for prefix in commercial_prefixes:
        if zoning_upper.startswith(prefix):
            return True
    # Also check description keywords
    commercial_keywords = ["commercial", "office", "industrial", "business", "mixed"]
    zoning_lower = zoning.lower()
    return any(kw in zoning_lower for kw in commercial_keywords)


def rank_contacts(result):
    """
    Take a property result dict and produce a ranked list of contacts.

    Each contact gets:
      - name, phone, email, linkedin
      - source: 'llc_principal', 'registered_agent', 'trestle', 'web_search', 'mgmt'
      - confidence: 'HIGH', 'MEDIUM', 'LOW'
      - label: human-readable role description
      - is_tenant: True if this is a tenant at a commercial property (for UI separation)

    Returns list sorted by confidence (HIGH first), with tenants separated out.
    """
    contacts = []
    is_commercial = _is_commercial_zoning(result.get("zoning", ""))

    # 1. LLC principal (person_name from SOS search) — usually the real owner
    llc_person = result.get("llc_person", "")
    if llc_person and is_person_name(llc_person):
        contacts.append({
            "name": llc_person,
            "phone": result.get("llc_phone", ""),
            "email": result.get("llc_email", ""),
            "linkedin": result.get("llc_linkedin", ""),
            "source": "llc_principal",
            "confidence": "HIGH",
            "label": "LLC Principal / Owner",
            "is_tenant": False,
        })

    # 2. Registered agent — could be a real person or a filing service
    reg_agent = result.get("llc_registered_agent", "")
    if reg_agent and reg_agent != llc_person:
        if is_filing_agent(reg_agent):
            contacts.append({
                "name": reg_agent,
                "phone": "",
                "email": "",
                "linkedin": "",
                "source": "registered_agent",
                "confidence": "LOW",
                "label": "Filing Agent (not decision-maker)",
                "is_tenant": False,
            })
        elif is_person_name(reg_agent):
            contacts.append({
                "name": reg_agent,
                "phone": "",
                "email": "",
                "linkedin": "",
                "source": "registered_agent",
                "confidence": "MEDIUM",
                "label": "Registered Agent (individual)",
                "is_tenant": False,
            })
        else:
            contacts.append({
                "name": reg_agent,
                "phone": "",
                "email": "",
                "linkedin": "",
                "source": "registered_agent",
                "confidence": "LOW",
                "label": "Filing Agent (not decision-maker)",
                "is_tenant": False,
            })

    # 3. Trestle residents/tenants
    # For commercial properties, these are TENANTS, not owner contacts
    for resident in result.get("trestle_residents", []):
        name = resident.get("name", "")
        if not name:
            continue
        phones = resident.get("phones", [])
        emails = resident.get("emails", [])

        if is_commercial:
            # Commercial property — Trestle results are tenants
            contacts.append({
                "name": name,
                "phone": phones[0]["number"] if phones else "",
                "email": emails[0] if emails else "",
                "linkedin": "",
                "source": "trestle",
                "confidence": "LOW",
                "label": "Tenant" if is_person_name(name) else "Business tenant",
                "is_tenant": True,
            })
        else:
            # Residential property — Trestle results may be the actual owner
            if is_person_name(name):
                has_contact = bool(phones or emails)
                contacts.append({
                    "name": name,
                    "phone": phones[0]["number"] if phones else "",
                    "email": emails[0] if emails else "",
                    "linkedin": "",
                    "source": "trestle",
                    "confidence": "HIGH" if has_contact else "MEDIUM",
                    "label": "Resident (verified at address)",
                    "is_tenant": False,
                })
            else:
                contacts.append({
                    "name": name,
                    "phone": phones[0]["number"] if phones else "",
                    "email": emails[0] if emails else "",
                    "linkedin": "",
                    "source": "trestle",
                    "confidence": "LOW",
                    "label": "Business at address",
                    "is_tenant": False,
                })

    # 4. Management company / leasing contacts
    if result.get("leasing_contact"):
        contacts.append({
            "name": result["leasing_contact"],
            "phone": result.get("mgmt_phone", ""),
            "email": result.get("mgmt_email", ""),
            "linkedin": "",
            "source": "mgmt",
            "confidence": "MEDIUM",
            "label": "Leasing Agent",
            "is_tenant": False,
        })
    elif result.get("mgmt_company"):
        contacts.append({
            "name": result["mgmt_company"],
            "phone": result.get("mgmt_phone", ""),
            "email": result.get("mgmt_email", ""),
            "linkedin": "",
            "source": "mgmt",
            "confidence": "LOW",
            "label": "Property Management Company",
            "is_tenant": False,
        })

    # Sort: non-tenants first, then HIGH > MEDIUM > LOW, then people before companies
    confidence_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    contacts.sort(key=lambda c: (
        1 if c.get("is_tenant") else 0,
        confidence_order.get(c["confidence"], 3),
        0 if is_person_name(c["name"]) else 1,
    ))

    return contacts
