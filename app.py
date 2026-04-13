"""
CRE Contact Finder — Web App
Find the person behind any commercial property in seconds.
Paste addresses → get owner, LLC principal, phone, email, LinkedIn.
"""

import os
import sys
import io
import csv
import json
import time
from datetime import datetime
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Load API keys from .env only — never hardcode secrets in source code

from skills.property_lookup import lookup_property
from skills.llc_lookup import lookup_llc
from skills.trestle_lookup import trestle_lookup
from utils.contact_ranking import rank_contacts
from utils.report import generate_report


# === Page Config ===
st.set_page_config(
    page_title="CRE Contact Finder",
    page_icon="🔍",
    layout="wide",
)


# === Styling ===
st.markdown("""
<style>
    .block-container { padding-top: 2rem; max-width: 1100px; }
    h1 { color: #0f3460; }

    /* Contact card */
    .contact-card {
        background: #f8f9fa;
        border-left: 4px solid #0f3460;
        padding: 16px 20px;
        margin-bottom: 12px;
        border-radius: 0 8px 8px 0;
    }
    .contact-card-hit {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
    }
    .contact-name {
        font-size: 18px;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 4px;
    }
    .contact-role {
        font-size: 14px;
        color: #6b7280;
        margin-bottom: 8px;
    }
    .contact-detail {
        font-size: 14px;
        color: #374151;
        margin: 2px 0;
    }
    .contact-detail a { color: #0f3460; text-decoration: none; }
    .contact-detail a:hover { text-decoration: underline; }

    /* Confidence badges */
    .badge-high {
        background: #dcfce7; color: #166534;
        padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
    }
    .badge-medium {
        background: #fef9c3; color: #854d0e;
        padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
    }
    .badge-low {
        background: #fecaca; color: #991b1b;
        padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
    }

    /* Property info (secondary) */
    .prop-detail {
        font-size: 13px; color: #6b7280; margin: 2px 0;
    }

    /* Stat cards */
    div[data-testid="stMetric"] {
        background: #f8f9fa;
        padding: 12px;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# === Header ===
st.title("CRE Contact Finder")
st.divider()

# === Mode Toggle ===
search_mode = st.radio(
    "What are you looking for?",
    ["Owner Lookup", "Tenant Research"],
    horizontal=True,
    help="Owner Lookup finds the person behind the LLC. Tenant Research shows who's leasing at the property.",
)

if search_mode == "Owner Lookup":
    st.markdown("**Find the person behind any commercial property — LLC principal, phone, email, LinkedIn.**")
else:
    st.markdown("**See every tenant and business at a property — names, phone numbers, business type.**")

st.divider()


# === Input Section ===
col_input, col_upload = st.columns([3, 1])

with col_input:
    address_text = st.text_area(
        "Property addresses (one per line)",
        height=150,
        placeholder="3500 Peachtree Rd, Atlanta, GA 30326\n2500 Old Milton Pkwy, Alpharetta, GA 30009\n980 Mansell Rd, Roswell, GA 30076",
    )

with col_upload:
    st.markdown("**Or upload a file**")
    uploaded_file = st.file_uploader(
        "Upload addresses (.txt or .csv)",
        type=["txt", "csv"],
        label_visibility="collapsed",
    )
    if uploaded_file:
        file_text = uploaded_file.read().decode("utf-8")
        if uploaded_file.name.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(file_text))
            addr_col = None
            for col in (reader.fieldnames or []):
                if "address" in col.lower():
                    addr_col = col
                    break
            if addr_col:
                addresses_from_file = [row[addr_col] for row in reader if row.get(addr_col, "").strip()]
                address_text = "\n".join(addresses_from_file)
            else:
                address_text = file_text
        else:
            address_text = file_text
        st.success(f"Loaded {len(address_text.strip().splitlines())} addresses from file")


# === Options Row ===
opt_col1, opt_col2 = st.columns([1, 3])
with opt_col1:
    generate_reports = st.checkbox("Generate PDF reports", value=False)
button_label = "Find Owner Contacts" if search_mode == "Owner Lookup" else "Find Tenants"
run_button = st.button(button_label, type="primary", use_container_width=True)


def _normalize_address(addr):
    """Normalize address formatting so users don't have to be exact."""
    import re
    addr = addr.strip()
    replacements = {
        r'\bParkway\b': 'Pkwy', r'\bPkwy\b': 'Pkwy', r'\bPky\b': 'Pkwy',
        r'\bStreet\b': 'St', r'\bDrive\b': 'Dr', r'\bAvenue\b': 'Ave',
        r'\bBoulevard\b': 'Blvd', r'\bRoad\b': 'Rd', r'\bLane\b': 'Ln',
        r'\bCircle\b': 'Cir', r'\bCourt\b': 'Ct', r'\bPlace\b': 'Pl',
        r'\bHighway\b': 'Hwy', r'\bTerrace\b': 'Ter', r'\bTrail\b': 'Trl',
    }
    for pattern, repl in replacements.items():
        addr = re.sub(pattern, repl, addr, flags=re.IGNORECASE)

    addr = re.sub(r'\b(North|South|East|West)(point|view|park|lake|ridge|wood|creek)\b',
                  lambda m: m.group(1) + ' ' + m.group(2).title(), addr, flags=re.IGNORECASE)

    if ',' not in addr:
        addr = _insert_commas(addr)

    parts = addr.split(',')
    normalized = []
    for i, part in enumerate(parts):
        part = part.strip()
        if i == 0:
            part = part.title()
        elif i == 1:
            part = part.strip().title()
        else:
            part = part.strip().upper()
        normalized.append(part)

    if len(normalized) == 1:
        return normalized[0]

    return ', '.join(normalized)


def _parse_address_parts(addr):
    """Parse a normalized address into parts."""
    import re
    parts = [p.strip() for p in addr.split(",")]
    if len(parts) < 2:
        return None
    street = parts[0]
    city = parts[1] if len(parts) >= 2 else ""
    state = ""
    zip_code = ""
    if len(parts) >= 3:
        state_zip = parts[2].strip()
        match = re.match(r'([A-Z]{2})\s*(\d{5})?', state_zip)
        if match:
            state = match.group(1)
            zip_code = match.group(2) or ""
    if not street or not city:
        return None
    return {"street": street, "city": city, "state": state, "zip": zip_code}


def _insert_commas(addr):
    """Insert commas into an address that has none."""
    import re

    _CITIES = [
        # Fulton / City-specific
        "Alpharetta", "Atlanta", "Roswell", "Sandy Springs", "Johns Creek",
        "Milton", "East Point", "College Park", "Union City", "Fairburn",
        "Hapeville", "Palmetto", "Chattahoochee Hills",
        # Cobb
        "Marietta", "Smyrna", "Kennesaw", "Acworth",
        "Powder Springs", "Austell", "Mableton",
        # Gwinnett
        "Duluth", "Lawrenceville", "Suwanee", "Norcross",
        "Peachtree Corners", "Lilburn", "Snellville", "Buford",
        "Dacula", "Grayson", "Loganville",
        # DeKalb
        "Dunwoody", "Brookhaven", "Decatur", "Tucker",
        "Stonecrest", "Chamblee", "Doraville", "Clarkston", "Lithonia",
        # Cherokee
        "Woodstock", "Canton", "Holly Springs", "Ball Ground",
        # Forsyth
        "Cumming", "Sugar Hill",
        # Henry
        "McDonough", "Stockbridge", "Hampton", "Locust Grove",
        # Douglas
        "Douglasville",
        # Hall
        "Gainesville", "Flowery Branch", "Oakwood",
        # Fayette
        "Fayetteville", "Peachtree City", "Tyrone",
        # Coweta
        "Newnan", "Senoia",
        # Jackson
        "Jefferson", "Hoschton", "Braselton",
        # Walton
        "Monroe", "Social Circle",
        # Chatham
        "Savannah", "Pooler", "Garden City", "Tybee Island",
    ]

    state_match = re.search(r'\b(GA|AL|TN|FL|SC|NC)\b\s*(\d{5})?', addr, re.IGNORECASE)
    state_pos = state_match.start() if state_match else len(addr)
    before_state = addr[:state_pos].strip()
    state_zip = addr[state_pos:].strip() if state_match else ""

    sorted_cities = sorted(_CITIES, key=len, reverse=True)
    for city in sorted_cities:
        idx = before_state.upper().rfind(city.upper())
        if idx > 0:
            street = before_state[:idx].strip()
            city_part = before_state[idx:].strip()
            if state_zip:
                return f"{street}, {city_part}, {state_zip}"
            return f"{street}, {city_part}"

    match = re.search(r'\b(GA|AL|TN|FL|SC|NC)\s*(\d{5})?', addr, re.IGNORECASE)
    if match:
        state_start = match.start()
        before_state = addr[:state_start].strip()
        state_zip = addr[state_start:].strip()

        street_types = r'\b(St|Rd|Dr|Ave|Blvd|Pkwy|Ln|Cir|Ct|Pl|Hwy|Ter|Trl|Way)\b'
        suffix_match = re.search(street_types, before_state, re.IGNORECASE)
        if suffix_match:
            split_at = suffix_match.end()
            street = before_state[:split_at].strip()
            city = before_state[split_at:].strip()
            if city:
                return f"{street}, {city}, {state_zip}"

    return addr


# === Run Research ===
if run_button:
    raw_addresses = [line.strip() for line in address_text.strip().splitlines() if line.strip()]
    addresses = [_normalize_address(a) for a in raw_addresses]

    if not addresses:
        st.warning("Please enter at least one address.")
        st.stop()

    missing_keys = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")
    if not os.environ.get("SERPAPI_KEY"):
        missing_keys.append("SERPAPI_KEY")
    if missing_keys:
        st.error(f"Missing API keys in .env: {', '.join(missing_keys)}")
        st.stop()

    st.divider()
    st.subheader(f"Researching {len(addresses)} {'address' if len(addresses) == 1 else 'addresses'}...")

    progress = st.progress(0, text="Starting research...")
    results = []

    for i, addr in enumerate(addresses):
        progress.progress(
            (i) / len(addresses),
            text=f"[{i+1}/{len(addresses)}] Finding contacts for {addr}",
        )

        prop = lookup_property(addr)

        # Flatten LLC details
        llc = prop.get("llc_details", {})
        prop["llc_person"] = llc.get("person_name", "")
        prop["llc_registered_agent"] = llc.get("registered_agent", "")
        prop["llc_principal_address"] = llc.get("principal_address", "")
        prop["llc_phone"] = llc.get("phone", "")
        prop["llc_email"] = llc.get("email", "")
        prop["llc_linkedin"] = llc.get("linkedin", "")
        prop["llc_filing_status"] = llc.get("filing_status", "")
        prop["llc_background"] = llc.get("background", "")

        # Flatten secondary contacts
        sec = prop.get("secondary_contacts", {})
        prop["mgmt_company"] = sec.get("mgmt_company", "")
        prop["leasing_contact"] = sec.get("leasing_contact", "")
        prop["mgmt_phone"] = sec.get("phone", "")
        prop["mgmt_email"] = sec.get("email", "")

        # Trestle reverse address lookup
        trestle_residents = []
        addr_parts = _parse_address_parts(addr)
        if addr_parts:
            trestle_residents = trestle_lookup(
                addr_parts["street"], addr_parts["city"],
                addr_parts["state"], addr_parts["zip"]
            )
        prop["trestle_residents"] = trestle_residents

        # Rank all contacts across sources
        prop["ranked_contacts"] = rank_contacts(prop)

        results.append({"address": addr, **prop})

    progress.progress(1.0, text="Done!")
    time.sleep(0.3)
    progress.empty()

    # Store results in session state
    st.session_state["results"] = results
    st.session_state["generate_reports"] = generate_reports
    st.session_state["search_mode"] = search_mode

    # === Auto-save results to disk ===
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

    csv_fields = [
        "address", "property_owner", "owner_mail_address",
        "best_contact", "contact_confidence", "contact_label",
        "best_phone", "best_email",
        "zoning", "zoning_uses", "parcel_id",
        "llc_person", "llc_registered_agent", "llc_principal_address",
        "llc_phone", "llc_email", "llc_linkedin", "llc_filing_status",
        "mgmt_company", "leasing_contact", "mgmt_phone", "mgmt_email",
        "data_source",
    ]
    csv_path = os.path.join(results_dir, f"{timestamp}_research.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in results:
            ranked = r.get("ranked_contacts", [])
            if ranked:
                best = ranked[0]
                r["best_contact"] = best["name"]
                r["contact_confidence"] = best["confidence"]
                r["contact_label"] = best["label"]
                r["best_phone"] = best.get("phone", "")
                r["best_email"] = best.get("email", "")
            writer.writerow(r)

    json_path = os.path.join(results_dir, f"{timestamp}_research.json")
    json_results = []
    for r in results:
        clean = {k: v for k, v in r.items() if isinstance(v, (str, int, float, bool, list, dict, type(None)))}
        json_results.append(clean)
    with open(json_path, "w") as f:
        json.dump(json_results, f, indent=2, default=str)

    st.success(f"Results auto-saved to `results/{timestamp}_research.csv`")


def _render_property_details(r):
    """Render property details and research links (shared by both modes)."""
    detail_col1, detail_col2 = st.columns(2)

    with detail_col1:
        zoning = r.get("zoning", "")
        zoning_uses = r.get("zoning_uses", "")
        parcel = r.get("parcel_id", "")
        mail_addr = r.get("owner_mail_address", "")
        source = r.get("data_source", "")

        if mail_addr:
            st.markdown(f"**Tax Mailing:** {mail_addr}")
        if zoning:
            st.markdown(f"**Zoning:** {zoning}")
        if zoning_uses:
            st.markdown(f"{zoning_uses}")
        if parcel:
            st.markdown(f"**Parcel ID:** {parcel}")
        if source:
            st.markdown(f"**Data Source:** {source}")

        if r.get("llc_principal_address") or r.get("llc_filing_status") or r.get("llc_background"):
            st.markdown("---")
            st.markdown("**LLC Details**")
            if r.get("llc_principal_address"):
                st.markdown(f"Principal Office: {r['llc_principal_address']}")
            if r.get("llc_filing_status"):
                st.markdown(f"Filing Status: {r['llc_filing_status']}")
            if r.get("llc_background"):
                st.markdown(f"Background: {r['llc_background']}")

    with detail_col2:
        st.markdown("**Research Links**")
        links = []
        if r.get("qpublic_link"):
            links.append(f"- [qPublic (property records)]({r['qpublic_link']})")
        if r.get("ga_sos_link"):
            links.append(f"- [GA Secretary of State (LLC)]({r['ga_sos_link']})")
        if r.get("gsccca_link"):
            links.append(f"- [GSCCCA (deed search)]({r['gsccca_link']})")
        if r.get("loopnet_link"):
            links.append(f"- [LoopNet]({r['loopnet_link']})")
        if r.get("assessor_link"):
            links.append(f"- [County Assessor]({r['assessor_link']})")
        if r.get("management_search"):
            links.append(f"- [Google: owner contacts]({r['management_search']})")
        if links:
            st.markdown("\n".join(links))
        else:
            st.markdown("_No links available_")


# === Display Results ===
if "results" in st.session_state and st.session_state["results"]:
    results = st.session_state["results"]
    mode = st.session_state.get("search_mode", "Owner Lookup")

    st.divider()

    if mode == "Tenant Research":
        # === TENANT RESEARCH MODE ===
        total = len(results)
        total_tenants = sum(len([c for c in r.get("ranked_contacts", []) if c.get("is_tenant")]) for r in results)
        total_businesses = sum(len([c for c in r.get("ranked_contacts", []) if c.get("is_tenant") and c.get("label") == "Business tenant"]) for r in results)
        total_with_phone = sum(len([c for c in r.get("ranked_contacts", []) if c.get("is_tenant") and c.get("phone")]) for r in results)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Properties", total)
        col2.metric("Total Tenants", total_tenants)
        col3.metric("Businesses", total_businesses)
        col4.metric("With Phone", total_with_phone)

        st.divider()

        for r in results:
            addr = r["address"]
            owner = r.get("property_owner", "")
            ranked = r.get("ranked_contacts", [])
            tenant_contacts = [c for c in ranked if c.get("is_tenant")]
            owner_contacts = [c for c in ranked if not c.get("is_tenant")]

            st.markdown(f"### {addr}")
            if owner:
                st.caption(f"Owner: {owner}")

            if tenant_contacts:
                # Separate businesses from individuals
                businesses = [c for c in tenant_contacts if c.get("label") == "Business tenant"]
                individuals = [c for c in tenant_contacts if c.get("label") != "Business tenant"]

                if businesses:
                    st.markdown(f"**Businesses ({len(businesses)})**")
                    for contact in businesses:
                        details = []
                        if contact.get("phone"):
                            details.append(f'<div class="contact-detail">Phone: <a href="tel:{contact["phone"]}">{contact["phone"]}</a></div>')
                        if contact.get("email"):
                            details.append(f'<div class="contact-detail">Email: <a href="mailto:{contact["email"]}">{contact["email"]}</a></div>')
                        details_html = "\n".join(details) if details else ""

                        st.markdown(f"""
                        <div class="contact-card">
                            <div class="contact-name">{contact['name']}</div>
                            {details_html}
                        </div>
                        """, unsafe_allow_html=True)

                if individuals:
                    st.markdown(f"**Individual Tenants ({len(individuals)})**")
                    for contact in individuals:
                        details = []
                        if contact.get("phone"):
                            details.append(f'<a href="tel:{contact["phone"]}">{contact["phone"]}</a>')
                        if contact.get("email"):
                            details.append(f'<a href="mailto:{contact["email"]}">{contact["email"]}</a>')
                        detail_str = " | ".join(details) if details else ""

                        st.markdown(f"""
                        <div class="contact-card">
                            <div class="contact-name">{contact['name']}</div>
                            <div class="contact-detail">{detail_str}</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown("_No tenants found at this address_")

            # Owner info collapsed
            if owner_contacts:
                with st.expander("Owner Contacts"):
                    for contact in owner_contacts:
                        parts = [f"**{contact['name']}** — {contact['label']}"]
                        if contact.get("phone"):
                            parts.append(f"Phone: {contact['phone']}")
                        if contact.get("email"):
                            parts.append(f"Email: {contact['email']}")
                        st.markdown(" | ".join(parts))

            with st.expander("Property Details & Research Links"):
                _render_property_details(r)

            st.divider()

    else:
        # === OWNER LOOKUP MODE ===
        total = len(results)
        contacts_found = sum(1 for r in results if any(not c.get("is_tenant") for c in r.get("ranked_contacts", [])))
        phones_found = sum(1 for r in results if any(c.get("phone") and not c.get("is_tenant") for c in r.get("ranked_contacts", [])))
        high_conf = sum(1 for r in results if any(c["confidence"] == "HIGH" and not c.get("is_tenant") for c in r.get("ranked_contacts", [])))

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Properties", total)
        col2.metric("Contacts Found", contacts_found)
        col3.metric("Phone Numbers", phones_found)
        col4.metric("High Confidence", high_conf)

        st.divider()

        for r in results:
            addr = r["address"]
            owner = r.get("property_owner", "")
            ranked = r.get("ranked_contacts", [])

            st.markdown(f"### {addr}")
            if owner:
                st.markdown(f"**Owner:** {owner}")

            owner_contacts = [c for c in ranked if not c.get("is_tenant")]
            tenant_contacts = [c for c in ranked if c.get("is_tenant")]

            if owner_contacts:
                for contact in owner_contacts:
                    conf = contact["confidence"]
                    if conf == "HIGH":
                        badge = '<span class="badge-high">HIGH</span>'
                        card_class = "contact-card contact-card-hit"
                    elif conf == "MEDIUM":
                        badge = '<span class="badge-medium">MEDIUM</span>'
                        card_class = "contact-card"
                    else:
                        badge = '<span class="badge-low">LOW</span>'
                        card_class = "contact-card"

                    details = []
                    if contact.get("phone"):
                        details.append(f'<div class="contact-detail">Phone: <a href="tel:{contact["phone"]}">{contact["phone"]}</a></div>')
                    if contact.get("email"):
                        details.append(f'<div class="contact-detail">Email: <a href="mailto:{contact["email"]}">{contact["email"]}</a></div>')
                    if contact.get("linkedin"):
                        details.append(f'<div class="contact-detail">LinkedIn: <a href="{contact["linkedin"]}" target="_blank">{contact["linkedin"]}</a></div>')

                    if not details and contact.get("source") == "llc_filing":
                        details.append('<div class="contact-detail" style="color:#6b7280;">No direct phone/email found — use the details above to research the entity</div>')

                    details_html = "\n".join(details) if details else '<div class="contact-detail" style="color:#9ca3af;">No direct contact info found</div>'

                    st.markdown(f"""
                    <div class="{card_class}">
                        <div class="contact-name">{contact['name']} {badge}</div>
                        <div class="contact-role">{contact['label']} — via {contact['source']}</div>
                        {details_html}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="contact-card">
                    <div class="contact-name" style="color:#9ca3af;">No owner contacts found</div>
                    <div class="contact-role">Try the research links below to search manually</div>
                </div>
                """, unsafe_allow_html=True)

            if tenant_contacts:
                with st.expander(f"Tenants at this address ({len(tenant_contacts)})"):
                    for contact in tenant_contacts:
                        details = []
                        if contact.get("phone"):
                            details.append(f'Phone: [{contact["phone"]}](tel:{contact["phone"]})')
                        if contact.get("email"):
                            details.append(f'Email: {contact["email"]}')
                        detail_str = " | ".join(details) if details else "_No contact info_"
                        st.markdown(f"- **{contact['name']}** — {contact['label']} — {detail_str}")

            with st.expander("Property Details & Research Links"):
                _render_property_details(r)

            st.divider()

    # === Downloads ===
    st.subheader("Export")
    dl_col1, dl_col2 = st.columns(2)

    # CSV download
    csv_fields = [
        "address", "property_owner", "owner_mail_address",
        "best_contact", "contact_confidence", "contact_label",
        "best_phone", "best_email",
        "zoning", "zoning_uses", "parcel_id",
        "llc_person", "llc_registered_agent", "llc_principal_address",
        "llc_phone", "llc_email", "llc_linkedin", "llc_filing_status",
        "mgmt_company", "leasing_contact", "mgmt_phone", "mgmt_email",
        "data_source", "management_search", "loopnet_link", "assessor_link",
        "qpublic_link", "ga_sos_link", "gsccca_link",
    ]
    csv_buffer = io.StringIO()
    writer = csv.DictWriter(csv_buffer, fieldnames=csv_fields, extrasaction="ignore")
    writer.writeheader()
    for r in results:
        ranked = r.get("ranked_contacts", [])
        if ranked:
            best = ranked[0]
            r["best_contact"] = best["name"]
            r["contact_confidence"] = best["confidence"]
            r["contact_label"] = best["label"]
            r["best_phone"] = best.get("phone", "")
            r["best_email"] = best.get("email", "")
        writer.writerow(r)

    dl_col1.download_button(
        label="Download CSV",
        data=csv_buffer.getvalue(),
        file_name="cre_contacts.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # PDF download
    if st.session_state.get("generate_reports"):
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        os.makedirs(report_dir, exist_ok=True)

        pdf_paths = []
        for r in results:
            filepath = generate_report(r, r["address"], output_dir=report_dir)
            pdf_paths.append(filepath)

        if len(pdf_paths) == 1:
            with open(pdf_paths[0], "rb") as f:
                dl_col2.download_button(
                    label="Download PDF Report",
                    data=f.read(),
                    file_name=os.path.basename(pdf_paths[0]),
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for path in pdf_paths:
                    zf.write(path, os.path.basename(path))
            dl_col2.download_button(
                label=f"Download {len(pdf_paths)} PDF Reports (ZIP)",
                data=zip_buffer.getvalue(),
                file_name="cre_reports.zip",
                mime="application/zip",
                use_container_width=True,
            )
    else:
        dl_col2.info("Check 'Generate PDF reports' before running to enable PDF downloads.")


# === Sidebar ===
with st.sidebar:
    st.markdown("### Two Modes")
    st.markdown(
        "**Owner Lookup** — Find the person behind the LLC. "
        "Pierces entity filings, finds principals, gets direct contact info. "
        "The part CoStar doesn't do.\n\n"
        "**Tenant Research** — See every business and tenant at a property. "
        "Find who's leasing, who might be expanding, who to approach for nearby space."
    )
    st.divider()
    st.markdown("### How It Works")
    st.markdown(
        "1. Looks up property owner (county GIS)\n"
        "2. Pierces the LLC (Secretary of State)\n"
        "3. Finds the principal's contact info\n"
        "4. Discovers all tenants at the address\n"
        "5. Ranks contacts by confidence"
    )
    st.divider()
    st.markdown("### Search History")
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if os.path.exists(results_dir):
        history_files = sorted(
            [f for f in os.listdir(results_dir) if f.endswith("_research.csv")],
            reverse=True,
        )
        if history_files:
            for hf in history_files[:10]:
                ts = hf.replace("_research.csv", "")
                try:
                    dt = datetime.strptime(ts, "%Y-%m-%d_%H%M%S")
                    label = dt.strftime("%b %d, %Y %I:%M %p")
                except ValueError:
                    label = ts
                filepath = os.path.join(results_dir, hf)
                with open(filepath, "rb") as f:
                    st.download_button(
                        label=f"{label}",
                        data=f.read(),
                        file_name=hf,
                        mime="text/csv",
                        key=f"history_{hf}",
                    )
        else:
            st.markdown("_No searches yet_")
    st.divider()
    st.markdown("### Coverage")
    st.markdown(
        "Optimized for **metro Atlanta** — 40+ cities across "
        "Fulton, Cobb, DeKalb, Gwinnett, Cherokee, and more.\n\n"
        "Other areas use web search fallback."
    )
