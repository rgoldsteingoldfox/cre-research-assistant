"""Terminal output formatting for CRE Research Assistant."""

import csv


DIVIDER = "=" * 60
THIN_DIVIDER = "-" * 60


def print_header(text):
    print(f"\n{DIVIDER}")
    print(f"  {text}")
    print(DIVIDER)


def print_business_list(businesses):
    """Print numbered list of businesses from Places API results."""
    print_header("BUSINESSES FOUND")
    print()
    for i, biz in enumerate(businesses, 1):
        phone = biz.get("phone", "")
        website = biz.get("website", "")
        print(f"  [{i:>2}] {biz['name']}")
        print(f"       {biz['address']}")
        if phone:
            print(f"       Phone: {phone}")
        if website:
            display_url = website if len(website) < 60 else website[:57] + "..."
            print(f"       Web:   {display_url}")
        print()


def print_deep_dive(biz, contacts, links, property_data=None):
    """Print detailed research output for a single business."""
    print(f"\n{DIVIDER}")
    print(f"  {biz['name']}")
    print(f"  {biz['address']}")
    print(DIVIDER)

    # ── DIRECT CONTACT ──
    print(f"\n  {THIN_DIVIDER}")
    print("  DIRECT CONTACT")
    print(f"  {THIN_DIVIDER}")

    print(f"\n  Phone:   {biz.get('phone') or 'not found'}")
    print(f"  Website: {biz.get('website') or 'not found'}")

    # ── BUSINESS OWNER ──
    print(f"\n  {THIN_DIVIDER}")
    print("  BUSINESS OWNER (TENANT)")
    print(f"  {THIN_DIVIDER}")

    if contacts.get("owner_name"):
        print(f"\n  >>> {contacts['owner_name']} <<<")
    else:
        print(f"\n  Not found")

    # ── ADDITIONAL CONTACTS ──
    if contacts.get("emails") or contacts.get("phones") or contacts.get("names"):
        print(f"\n  {THIN_DIVIDER}")
        print("  ADDITIONAL CONTACTS (from website)")
        print(f"  {THIN_DIVIDER}")

        if contacts.get("emails"):
            for email in contacts["emails"]:
                print(f"\n  Email: {email}")
        if contacts.get("phones"):
            for phone in contacts["phones"]:
                print(f"  Phone: {phone}")
        if contacts.get("names"):
            for name in contacts["names"]:
                print(f"  Name:  {name}")

    # ── PROPERTY OWNER / LANDLORD ──
    print(f"\n  {THIN_DIVIDER}")
    print("  PROPERTY OWNER / LANDLORD")
    print(f"  {THIN_DIVIDER}")

    if property_data:
        if property_data.get("property_owner"):
            print(f"\n  >>> {property_data['property_owner']} <<<")
        else:
            print(f"\n  Not found")

        if property_data.get("owner_mail_address"):
            print(f"  Tax Mailing Addr: {property_data['owner_mail_address']}")

        if property_data.get("zoning"):
            print(f"  Zoning: {property_data['zoning']}")
        if property_data.get("zoning_uses"):
            print(f"  {property_data['zoning_uses']}")
        if property_data.get("parcel_id"):
            print(f"  Parcel: {property_data['parcel_id']}")
        if property_data.get("data_source"):
            print(f"  Source: {property_data['data_source']}")

        # Secondary contacts (mgmt company, leasing agent, etc.)
        sec = property_data.get("secondary_contacts", {})
        if any(sec.values()):
            print(f"\n  {THIN_DIVIDER}")
            print("  PROPERTY MANAGEMENT / LEASING")
            print(f"  {THIN_DIVIDER}")
            if sec.get("mgmt_company"):
                print(f"\n  Management Co: {sec['mgmt_company']}")
            if sec.get("leasing_contact"):
                print(f"  Leasing Agent: {sec['leasing_contact']}")
            if sec.get("phone"):
                print(f"  Phone:         {sec['phone']}")
            if sec.get("email"):
                print(f"  Email:         {sec['email']}")
        # LLC details (person behind the entity)
        llc = property_data.get("llc_details", {})
        if llc and (llc.get("person_name") or llc.get("registered_agent")):
            print(f"\n  {THIN_DIVIDER}")
            print("  PERSON BEHIND THE LLC")
            print(f"  {THIN_DIVIDER}")

            if llc.get("person_name"):
                print(f"\n  >>> {llc['person_name']} <<<")
            if llc.get("registered_agent") and llc["registered_agent"] != llc.get("person_name"):
                print(f"  Registered Agent: {llc['registered_agent']}")
            if llc.get("principal_address"):
                print(f"  Principal Office: {llc['principal_address']}")
            if llc.get("filing_status"):
                print(f"  Filing Status:    {llc['filing_status']}")
            if llc.get("phone"):
                print(f"  Phone:            {llc['phone']}")
            if llc.get("email"):
                print(f"  Email:            {llc['email']}")
            if llc.get("linkedin"):
                print(f"  LinkedIn:         {llc['linkedin']}")
    else:
        print("\n  (Property lookup not run)")

    # ── RESEARCH LINKS ──
    print(f"\n  {THIN_DIVIDER}")
    print("  RESEARCH LINKS")
    print(f"  {THIN_DIVIDER}")

    if links.get("owner_search"):
        print(f"\n  Business owner:    {links['owner_search']}")
    if links.get("property_search"):
        print(f"  Property owner:    {links['property_search']}")
    if links.get("leasing_search"):
        print(f"  Leasing:           {links['leasing_search']}")
    if links.get("property_manager_search"):
        print(f"  Property manager:  {links['property_manager_search']}")
    if links.get("zoning_search"):
        print(f"  Zoning:            {links['zoning_search']}")

    # Quick lookup links
    if property_data:
        if property_data.get("loopnet_link"):
            print(f"  LoopNet:           {property_data['loopnet_link']}")
        if property_data.get("assessor_link"):
            print(f"  County assessor:   {property_data['assessor_link']}")
    if links.get("county"):
        print(f"  County:            {links['county']}")

    # === DIRECT LOOKUP LINKS ===
    has_direct = any(links.get(k) for k in ["qpublic", "municode", "ga_sos", "gsccca"])
    if has_direct or (property_data and property_data.get("qpublic_link")):
        print(f"\n  {THIN_DIVIDER}")
        print("  DIRECT LOOKUP LINKS")
        print(f"  {THIN_DIVIDER}")

        qpublic = (property_data or {}).get("qpublic_link") or links.get("qpublic", "")
        if qpublic:
            print(f"\n  qPublic (owner):   {qpublic}")
        if links.get("municode"):
            print(f"  Municode (zoning): {links['municode']}")
        if links.get("ga_sos"):
            print(f"  GA SOS (LLC):      {links['ga_sos']}")
        if links.get("gsccca"):
            print(f"  GSCCCA (deeds):    {links['gsccca']}")

    print()


def export_csv(filepath, businesses, research_data=None):
    """Export results to CSV file."""
    fieldnames = [
        "name", "address", "phone", "website",
        "business_owner", "emails_found", "phones_found",
        "property_owner", "owner_mail_address", "zoning", "zoning_uses", "parcel_id",
        "llc_person", "llc_registered_agent", "llc_principal_address",
        "llc_phone", "llc_email", "llc_linkedin", "llc_filing_status",
        "mgmt_company", "leasing_contact", "mgmt_phone", "mgmt_email",
        "loopnet_link", "assessor_link",
        "qpublic_link", "municode_link", "ga_sos_link", "gsccca_link",
        "county",
        "owner_search_link", "property_search_link",
        "leasing_search_link", "property_manager_search_link",
        "zoning_search_link",
    ]

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for biz in businesses:
            row = {
                "name": biz["name"],
                "address": biz["address"],
                "phone": biz.get("phone", ""),
                "website": biz.get("website", ""),
            }

            key = biz["name"]
            if research_data and key in research_data:
                contacts = research_data[key].get("contacts", {})
                links = research_data[key].get("links", {})
                prop = research_data[key].get("property", {})
                sec = prop.get("secondary_contacts", {})

                row["business_owner"] = contacts.get("owner_name", "")
                row["emails_found"] = " | ".join(contacts.get("emails", []))
                row["phones_found"] = " | ".join(contacts.get("phones", []))
                row["property_owner"] = prop.get("property_owner", "")
                row["owner_mail_address"] = prop.get("owner_mail_address", "")
                row["zoning"] = prop.get("zoning", "")
                row["zoning_uses"] = prop.get("zoning_uses", "")
                row["parcel_id"] = prop.get("parcel_id", "")
                row["mgmt_company"] = sec.get("mgmt_company", "")
                row["leasing_contact"] = sec.get("leasing_contact", "")
                row["mgmt_phone"] = sec.get("phone", "")
                row["mgmt_email"] = sec.get("email", "")
                llc = prop.get("llc_details", {})
                row["llc_person"] = llc.get("person_name", "")
                row["llc_registered_agent"] = llc.get("registered_agent", "")
                row["llc_principal_address"] = llc.get("principal_address", "")
                row["llc_phone"] = llc.get("phone", "")
                row["llc_email"] = llc.get("email", "")
                row["llc_linkedin"] = llc.get("linkedin", "")
                row["llc_filing_status"] = llc.get("filing_status", "")
                row["loopnet_link"] = prop.get("loopnet_link", "")
                row["assessor_link"] = prop.get("assessor_link", "")
                row["qpublic_link"] = prop.get("qpublic_link", "") or links.get("qpublic", "")
                row["municode_link"] = links.get("municode", "")
                row["ga_sos_link"] = links.get("ga_sos", "")
                row["gsccca_link"] = links.get("gsccca", "")
                row["county"] = links.get("county", "")
                row["owner_search_link"] = links.get("owner_search", "")
                row["property_search_link"] = links.get("property_search", "")
                row["leasing_search_link"] = links.get("leasing_search", "")
                row["property_manager_search_link"] = links.get("property_manager_search", "")
                row["zoning_search_link"] = links.get("zoning_search", "")

            writer.writerow(row)

    print(f"\n  CSV saved to: {filepath}")
