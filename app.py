"""
CRE Research Assistant — Web App
Streamlit interface for property intelligence research.
"""

import os
import sys
import io
import csv
import time
import streamlit as st

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Load Streamlit Cloud secrets into env vars (for deployment)
try:
    for key in ["GOOGLE_API_KEY", "SERPAPI_KEY", "ANTHROPIC_API_KEY"]:
        if key in st.secrets and not os.environ.get(key):
            os.environ[key] = st.secrets[key]
except Exception:
    pass  # Not on Streamlit Cloud, using .env instead

from skills.property_lookup import lookup_property
from skills.llc_lookup import lookup_llc
from utils.report import generate_report


# === Page Config ===
st.set_page_config(
    page_title="CRE Research Assistant",
    page_icon="🏢",
    layout="wide",
)


# === Styling ===
st.markdown("""
<style>
    /* Clean up the default Streamlit look */
    .block-container { padding-top: 2rem; max-width: 1100px; }
    h1 { color: #0f3460; }
    .stDataFrame { font-size: 14px; }

    /* Status badges */
    .badge-found {
        background: #d4edda; color: #155724;
        padding: 2px 8px; border-radius: 4px; font-size: 13px;
    }
    .badge-missing {
        background: #f8d7da; color: #721c24;
        padding: 2px 8px; border-radius: 4px; font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)


# === Header ===
st.title("CRE Research Assistant")
st.markdown("Paste property addresses below to get owner, zoning, LLC, and contact intelligence.")
st.divider()


# === Input Section ===
col_input, col_upload = st.columns([3, 1])

with col_input:
    address_text = st.text_area(
        "Addresses (one per line)",
        height=180,
        placeholder="1090 Alpharetta St, Roswell, GA 30075\n585 Atlanta St, Roswell, GA 30075\n7900 North Point Pkwy, Alpharetta, GA 30005",
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
        # If CSV, try to extract an "address" column; otherwise treat as one-per-line
        if uploaded_file.name.endswith(".csv"):
            reader = csv.DictReader(io.StringIO(file_text))
            # Look for an address column
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


# === Research Button ===
generate_reports = st.checkbox("Generate PDF reports", value=False)
run_button = st.button("Research Addresses", type="primary", use_container_width=True)


# === Run Research ===
if run_button:
    # Parse addresses
    addresses = [line.strip() for line in address_text.strip().splitlines() if line.strip()]

    if not addresses:
        st.warning("Please enter at least one address.")
        st.stop()

    # Check for API keys
    missing_keys = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        missing_keys.append("ANTHROPIC_API_KEY")
    if not os.environ.get("SERPAPI_KEY"):
        missing_keys.append("SERPAPI_KEY")
    if missing_keys:
        st.error(f"Missing API keys in .env: {', '.join(missing_keys)}")
        st.stop()

    st.divider()
    st.subheader(f"Researching {len(addresses)} addresses")

    progress = st.progress(0, text="Starting research...")
    results = []

    for i, addr in enumerate(addresses):
        progress.progress(
            (i) / len(addresses),
            text=f"[{i+1}/{len(addresses)}] {addr}",
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

        results.append({"address": addr, **prop})

    progress.progress(1.0, text="Done!")
    time.sleep(0.3)
    progress.empty()

    # Store results in session state for persistence
    st.session_state["results"] = results
    st.session_state["generate_reports"] = generate_reports


# === Display Results ===
if "results" in st.session_state and st.session_state["results"]:
    results = st.session_state["results"]

    st.divider()

    # Summary stats
    found = sum(1 for r in results if r.get("property_owner"))
    zoned = sum(1 for r in results if r.get("zoning"))
    llc_found = sum(1 for r in results if r.get("llc_person"))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Addresses", len(results))
    col2.metric("Owners Found", found)
    col3.metric("Zoning Found", zoned)
    col4.metric("LLC Contacts", llc_found)

    st.divider()

    # === Results Cards ===
    for r in results:
        addr = r["address"]
        owner = r.get("property_owner", "")
        zoning = r.get("zoning", "")
        zoning_uses = r.get("zoning_uses", "")
        parcel = r.get("parcel_id", "")
        mail_addr = r.get("owner_mail_address", "")
        source = r.get("data_source", "")

        with st.expander(f"**{addr}** — {owner or 'No owner found'}", expanded=True):
            col_left, col_right = st.columns(2)

            with col_left:
                st.markdown("**Property Overview**")
                if owner:
                    st.markdown(f"- **Owner:** {owner}")
                else:
                    st.markdown("- **Owner:** _Not found_")
                if mail_addr:
                    st.markdown(f"- **Tax Mailing:** {mail_addr}")
                if zoning:
                    st.markdown(f"- **Zoning:** {zoning}")
                if zoning_uses:
                    st.markdown(f"- {zoning_uses}")
                if parcel:
                    st.markdown(f"- **Parcel ID:** {parcel}")
                if source:
                    st.markdown(f"- **Source:** {source}")

            with col_right:
                # LLC details
                if r.get("llc_person") or r.get("llc_registered_agent"):
                    st.markdown("**Person Behind the LLC**")
                    if r.get("llc_person"):
                        st.markdown(f"- **Person:** {r['llc_person']}")
                    if r.get("llc_registered_agent") and r["llc_registered_agent"] != r.get("llc_person"):
                        st.markdown(f"- **Registered Agent:** {r['llc_registered_agent']}")
                    if r.get("llc_principal_address"):
                        st.markdown(f"- **Principal Office:** {r['llc_principal_address']}")
                    if r.get("llc_filing_status"):
                        st.markdown(f"- **Filing Status:** {r['llc_filing_status']}")
                    if r.get("llc_phone"):
                        st.markdown(f"- **Phone:** {r['llc_phone']}")
                    if r.get("llc_email"):
                        st.markdown(f"- **Email:** {r['llc_email']}")
                    if r.get("llc_linkedin"):
                        st.markdown(f"- **LinkedIn:** [{r['llc_linkedin']}]({r['llc_linkedin']})")
                    if r.get("llc_background"):
                        st.markdown(f"- **Background:** {r['llc_background']}")

                # Management / leasing
                if r.get("mgmt_company") or r.get("leasing_contact"):
                    st.markdown("**Property Management / Leasing**")
                    if r.get("mgmt_company"):
                        st.markdown(f"- **Management Co:** {r['mgmt_company']}")
                    if r.get("leasing_contact"):
                        st.markdown(f"- **Leasing Agent:** {r['leasing_contact']}")
                    if r.get("mgmt_phone"):
                        st.markdown(f"- **Phone:** {r['mgmt_phone']}")
                    if r.get("mgmt_email"):
                        st.markdown(f"- **Email:** {r['mgmt_email']}")

                if not r.get("llc_person") and not r.get("mgmt_company"):
                    st.markdown("**Contacts**")
                    st.markdown("_No additional contacts found_")

            # Research links row
            link_cols = st.columns(5)
            if r.get("qpublic_link"):
                link_cols[0].markdown(f"[qPublic]({r['qpublic_link']})")
            if r.get("ga_sos_link"):
                link_cols[1].markdown(f"[GA SOS]({r['ga_sos_link']})")
            if r.get("gsccca_link"):
                link_cols[2].markdown(f"[GSCCCA Deeds]({r['gsccca_link']})")
            if r.get("loopnet_link"):
                link_cols[3].markdown(f"[LoopNet]({r['loopnet_link']})")
            if r.get("assessor_link"):
                link_cols[4].markdown(f"[County Assessor]({r['assessor_link']})")

    st.divider()

    # === Downloads ===
    st.subheader("Download Results")
    dl_col1, dl_col2 = st.columns(2)

    # CSV download
    csv_fields = [
        "address", "property_owner", "owner_mail_address",
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
        writer.writerow(r)

    dl_col1.download_button(
        label="Download CSV",
        data=csv_buffer.getvalue(),
        file_name="cre_research_results.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # PDF download (generate for each result)
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
            # Bundle multiple PDFs into a zip
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
    st.markdown("### About")
    st.markdown(
        "CRE Research Assistant finds **property owners**, "
        "**zoning data**, **LLC principals**, and **contact info** "
        "for commercial real estate addresses."
    )
    st.divider()
    st.markdown("### How it works")
    st.markdown(
        "1. Paste addresses (one per line)\n"
        "2. Click **Research Addresses**\n"
        "3. Review results and download CSV/PDF"
    )
    st.divider()
    st.markdown("### Data Sources")
    st.markdown(
        "- City ArcGIS (owner, zoning, parcel)\n"
        "- Google Search via SerpAPI\n"
        "- GA Secretary of State (LLC)\n"
        "- Website scraping (contacts)\n"
        "- AI extraction (Claude Haiku)"
    )
    st.divider()
    st.markdown(
        "<small>Built by CRE Research Assistant</small>",
        unsafe_allow_html=True,
    )
