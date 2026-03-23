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
            print(f"\n  Not found via search")

        if property_data.get("zoning"):
            zoning_lines = property_data["zoning"].split("\n")
            print(f"  Zoning: {zoning_lines[0]}")
            if len(zoning_lines) > 1:
                print(f"  {zoning_lines[1]}")

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

    print()


def export_csv(filepath, businesses, research_data=None):
    """Export results to CSV file."""
    fieldnames = [
        "name", "address", "phone", "website",
        "business_owner", "emails_found", "phones_found",
        "property_owner", "zoning",
        "mgmt_company", "leasing_contact", "mgmt_phone", "mgmt_email",
        "loopnet_link", "assessor_link",
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
                row["zoning"] = prop.get("zoning", "")
                row["mgmt_company"] = sec.get("mgmt_company", "")
                row["leasing_contact"] = sec.get("leasing_contact", "")
                row["mgmt_phone"] = sec.get("phone", "")
                row["mgmt_email"] = sec.get("email", "")
                row["loopnet_link"] = prop.get("loopnet_link", "")
                row["assessor_link"] = prop.get("assessor_link", "")
                row["county"] = links.get("county", "")
                row["owner_search_link"] = links.get("owner_search", "")
                row["property_search_link"] = links.get("property_search", "")
                row["leasing_search_link"] = links.get("leasing_search", "")
                row["property_manager_search_link"] = links.get("property_manager_search", "")
                row["zoning_search_link"] = links.get("zoning_search", "")

            writer.writerow(row)

    print(f"\n  CSV saved to: {filepath}")
