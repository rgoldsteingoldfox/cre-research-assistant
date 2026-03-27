"""Generate professional PDF property intelligence reports."""

import os
import re
from datetime import date

import fitz  # pymupdf


# Colors
NAVY = (15/255, 52/255, 96/255)
DARK = (26/255, 26/255, 46/255)
GRAY = (85/255, 85/255, 85/255)
LIGHT_GRAY = (170/255, 170/255, 170/255)
BG_GRAY = (248/255, 249/255, 251/255)
LINE_GRAY = (224/255, 224/255, 224/255)
HIGHLIGHT_BG = (238/255, 243/255, 255/255)
WHITE = (1, 1, 1)

# Page dimensions
WIDTH, HEIGHT = 612, 792  # Letter
MARGIN = 54
LABEL_W = 200
VAL_X = MARGIN + LABEL_W + 12


def generate_report(property_data, address, output_dir="reports"):
    """
    Generate a PDF property intelligence report.
    property_data: dict from lookup_property()
    address: the original address string
    output_dir: where to save the PDF
    Returns the output file path.
    """
    os.makedirs(output_dir, exist_ok=True)

    slug = re.sub(r'[^a-zA-Z0-9]+', '_', address.split(",")[0].strip())
    filename = f"{slug}_Report.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = fitz.open()
    ctx = {"doc": doc, "page": doc.new_page(width=WIDTH, height=HEIGHT), "y": MARGIN}

    # === HEADER ===
    _draw_header(ctx, address)

    # === PROPERTY OVERVIEW ===
    owner = property_data.get("property_owner", "")
    zoning = property_data.get("zoning", "")
    zoning_uses = property_data.get("zoning_uses", "")
    parcel = property_data.get("parcel_id", "")
    mail_addr = property_data.get("owner_mail_address", "")

    _draw_section_header(ctx, "PROPERTY OVERVIEW")
    if zoning:
        # Clean up the zoning display
        zoning_display = zoning
        if zoning_uses:
            # Strip "Typical uses: " prefix if present, we'll add our own label
            uses = re.sub(r'^Typical uses:\s*', '', zoning_uses, flags=re.IGNORECASE)
            zoning_display = f"{zoning} — {uses}"
        _draw_info_row(ctx, "Zoning", zoning_display)
    if parcel:
        _draw_info_row(ctx, "Parcel ID", parcel)
    ctx["y"] += 12

    # === OWNERSHIP ===
    _draw_section_header(ctx, "OWNERSHIP")
    if owner:
        _draw_info_row(ctx, "Owner", owner, highlight=True)
    if mail_addr:
        _draw_info_row(ctx, "Tax Mailing Address", mail_addr)

    # LLC details
    llc = property_data.get("llc_details", {})
    if llc:
        if llc.get("person_name"):
            _draw_info_row(ctx, "Principals", llc["person_name"], highlight=True)
        if llc.get("registered_agent") and llc["registered_agent"] != llc.get("person_name"):
            _draw_info_row(ctx, "Registered Agent", llc["registered_agent"])
        if llc.get("principal_address"):
            _draw_info_row(ctx, "Principal Office", llc["principal_address"])
        if llc.get("filing_status"):
            _draw_info_row(ctx, "Filing Status", llc["filing_status"])
        if llc.get("phone"):
            _draw_info_row(ctx, "Phone", llc["phone"])
        if llc.get("email"):
            _draw_info_row(ctx, "Email", llc["email"])
        if llc.get("linkedin"):
            _draw_info_row(ctx, "LinkedIn", llc["linkedin"])

    # Secondary contacts
    sec = property_data.get("secondary_contacts", {})
    if any(sec.values()):
        ctx["y"] += 12
        _draw_section_header(ctx, "PROPERTY MANAGEMENT / LEASING")
        if sec.get("mgmt_company"):
            _draw_info_row(ctx, "Management Co.", sec["mgmt_company"])
        if sec.get("leasing_contact"):
            _draw_info_row(ctx, "Leasing Agent", sec["leasing_contact"])
        if sec.get("phone"):
            _draw_info_row(ctx, "Phone", sec["phone"])
        if sec.get("email"):
            _draw_info_row(ctx, "Email", sec["email"])

    ctx["y"] += 12

    # === RECOMMENDED NEXT STEPS (auto-generated based on what we found) ===
    steps = _build_next_steps(property_data)
    if steps:
        _ensure_space(ctx, 30 + 28 * len(steps))
        _draw_section_header(ctx, "RECOMMENDED NEXT STEPS")
        _draw_numbered_steps(ctx, steps)

    ctx["y"] += 12

    # === DATA SOURCES ===
    sources = _build_sources(property_data)
    if sources:
        _ensure_space(ctx, 30 + 18 * len(sources))
        _draw_section_header(ctx, "DATA SOURCES")
        for src, detail in sources:
            _draw_source_row(ctx, src, detail)

    # === FOOTER ===
    _draw_footer_at_bottom(ctx)

    doc.save(filepath)
    doc.close()
    return filepath


def _build_next_steps(data):
    """Auto-generate recommended next steps based on what data we found."""
    steps = []
    owner = data.get("property_owner", "")
    mail_addr = data.get("owner_mail_address", "")
    llc = data.get("llc_details", {})
    sec = data.get("secondary_contacts", {})

    # If we found a management company, that's the #1 contact
    if sec.get("mgmt_company"):
        mgmt = sec["mgmt_company"]
        detail = f"Contact {mgmt}"
        if sec.get("phone"):
            detail += f" at {sec['phone']}"
        if sec.get("leasing_contact"):
            detail += f" (ask for {sec['leasing_contact']})"
        steps.append(("Property Manager", detail))

    # If we have LLC person with contact info
    if llc.get("person_name"):
        person = llc["person_name"]
        if llc.get("phone") or llc.get("email"):
            contact_parts = []
            if llc.get("phone"):
                contact_parts.append(llc["phone"])
            if llc.get("email"):
                contact_parts.append(llc["email"])
            steps.append(("Direct Contact", f"Reach {person} at {' / '.join(contact_parts)}"))
        elif llc.get("linkedin"):
            steps.append(("LinkedIn", f"Connect with {person} on LinkedIn"))

    # If owner is an LLC, suggest SOS lookup
    if owner and any(ind in owner.upper() for ind in ["LLC", "INC", "CORP", "LP", "TRUST", "GROUP", "HOLDINGS"]):
        steps.append(("LLC Lookup", f'Search "{owner}" on GA Secretary of State (ecorp.sos.ga.gov) for registered agent and filing details'))

    # If we have a mailing address
    if mail_addr:
        # Check if mailing address differs from property address (out-of-state owner)
        steps.append(("Direct Mail", f"Send letter to {mail_addr}"))

    # Always suggest qPublic for verification
    if data.get("qpublic_link"):
        steps.append(("Verify Ownership", "Confirm owner of record on Fulton County qPublic (free, no login required)"))

    return steps


def _build_sources(data):
    """Build list of data sources used."""
    sources = []
    source = data.get("data_source", "")
    if "ArcGIS" in source:
        city = re.search(r'\((.+)\)', source)
        city_name = city.group(1) if city else "City"
        sources.append((f"City of {city_name} ArcGIS", "Owner, mailing address, zoning, parcel, appraisal"))
    elif "SerpAPI" in source:
        sources.append(("Google Search (SerpAPI)", "Owner and zoning from web search results"))

    if data.get("llc_details", {}).get("person_name"):
        sources.append(("LLC Registration Search", "Registered agent, principals, filing status"))

    if data.get("secondary_contacts", {}).get("mgmt_company"):
        sources.append(("Web Search", "Property management and leasing contacts"))

    if data.get("zoning_uses"):
        sources.append(("AI Zoning Interpretation", "Typical permitted uses for zoning classification"))

    return sources


# === Drawing helpers ===

def _ensure_space(ctx, needed):
    """Add a new page if not enough space remaining."""
    if ctx["y"] + needed > HEIGHT - 60:
        ctx["page"] = ctx["doc"].new_page(width=WIDTH, height=HEIGHT)
        ctx["y"] = MARGIN


def _draw_header(ctx, address):
    page, y = ctx["page"], ctx["y"]
    page.insert_text(
        (MARGIN, y + 22), "PROPERTY INTELLIGENCE REPORT",
        fontsize=22, fontname="Helvetica-Bold", color=NAVY,
    )
    y += 34
    page.insert_text(
        (MARGIN, y + 14), address,
        fontsize=13, fontname="Helvetica", color=GRAY,
    )
    y += 20
    today = date.today().strftime("%B %d, %Y")
    page.insert_text(
        (MARGIN, y + 10), f"Prepared {today}",
        fontsize=10, fontname="Helvetica-Oblique", color=LIGHT_GRAY,
    )
    y += 18
    page.draw_line((MARGIN, y), (WIDTH - MARGIN, y), color=NAVY, width=2.5)
    y += 20
    ctx["y"] = y


def _draw_section_header(ctx, text):
    _ensure_space(ctx, 40)
    page, y = ctx["page"], ctx["y"]
    page.insert_text(
        (MARGIN, y + 12), text,
        fontsize=11, fontname="Helvetica-Bold", color=NAVY,
    )
    y += 16
    page.draw_line((MARGIN, y), (WIDTH - MARGIN, y), color=LINE_GRAY, width=1)
    y += 10
    ctx["y"] = y


def _draw_info_row(ctx, label, value, highlight=False):
    """Draw a label-value row with word wrapping."""
    max_val_width = WIDTH - VAL_X - MARGIN
    chars_per_line = int(max_val_width / 5.5)

    lines = _wrap_text(value, chars_per_line)
    row_h = max(22, 14 * len(lines) + 8)

    _ensure_space(ctx, row_h)
    page, y = ctx["page"], ctx["y"]

    bg = HIGHLIGHT_BG if highlight else BG_GRAY

    # Label background
    page.draw_rect(fitz.Rect(MARGIN, y, MARGIN + LABEL_W, y + row_h), color=None, fill=bg)
    # Label right border
    page.draw_line((MARGIN + LABEL_W, y), (MARGIN + LABEL_W, y + row_h), color=NAVY, width=1.5)
    # Bottom border
    page.draw_line((MARGIN, y + row_h), (WIDTH - MARGIN, y + row_h), color=LINE_GRAY, width=0.5)

    page.insert_text(
        (MARGIN + 8, y + 14), label,
        fontsize=10, fontname="Helvetica-Bold", color=DARK,
    )

    for i, line in enumerate(lines):
        page.insert_text(
            (VAL_X, y + 14 + (i * 14)), line,
            fontsize=10, fontname="Helvetica", color=GRAY,
        )

    ctx["y"] = y + row_h


def _draw_numbered_steps(ctx, steps):
    """Draw numbered next steps with priority badges."""
    for i, (channel, detail) in enumerate(steps, 1):
        lines = _wrap_text(detail, 52)
        row_h = max(26, 13 * len(lines) + 14)

        _ensure_space(ctx, row_h)
        page, y = ctx["page"], ctx["y"]

        # Bottom border
        page.draw_line((MARGIN, y + row_h), (WIDTH - MARGIN, y + row_h), color=LINE_GRAY, width=0.5)

        # Number
        page.insert_text(
            (MARGIN + 16, y + 15), str(i),
            fontsize=12, fontname="Helvetica-Bold", color=NAVY,
        )

        # Channel label
        page.insert_text(
            (MARGIN + 50, y + 15), channel,
            fontsize=10, fontname="Helvetica-Bold", color=DARK,
        )

        # Detail text
        for j, line in enumerate(lines):
            page.insert_text(
                (MARGIN + 170, y + 15 + (j * 13)), line,
                fontsize=9, fontname="Helvetica", color=GRAY,
            )

        ctx["y"] = y + row_h


def _draw_source_row(ctx, source, detail):
    """Draw a compact data source row."""
    _ensure_space(ctx, 20)
    page, y = ctx["page"], ctx["y"]

    page.draw_line((MARGIN, y + 18), (WIDTH - MARGIN, y + 18), color=LINE_GRAY, width=0.5)
    page.insert_text(
        (MARGIN + 8, y + 12), source,
        fontsize=9, fontname="Helvetica-Bold", color=DARK,
    )
    page.insert_text(
        (MARGIN + 230, y + 12), detail,
        fontsize=9, fontname="Helvetica", color=GRAY,
    )
    ctx["y"] = y + 18


def _draw_footer_at_bottom(ctx):
    """Draw footer at the bottom of the current page."""
    page = ctx["page"]
    y = HEIGHT - 60
    page.draw_line((MARGIN, y), (WIDTH - MARGIN, y), color=LINE_GRAY, width=1)
    y += 14
    footer = (
        "Report generated by CRE Research Assistant "
        "— AI-powered property intelligence for commercial real estate professionals."
    )
    page.insert_text(
        (MARGIN + 10, y + 10), footer,
        fontsize=9, fontname="Helvetica-Oblique", color=LIGHT_GRAY,
    )


def _wrap_text(text, chars_per_line):
    """Word-wrap text to fit within a given character width."""
    if len(text) <= chars_per_line:
        return [text]

    lines = []
    words = text.split(" ")
    current = ""
    for w in words:
        if len(current + " " + w) > chars_per_line and current:
            lines.append(current.strip())
            current = w
        else:
            current = current + " " + w if current else w
    if current:
        lines.append(current.strip())
    return lines
