"""Terminal output formatting for CRE Research Assistant."""

import csv
import io


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
            # Truncate long URLs for display
            display_url = website if len(website) < 60 else website[:57] + "..."
            print(f"       Web:   {display_url}")
        print()


def print_deep_dive(biz, contacts, links, property_data=None):
    """Print detailed research output for a single business."""
    print(f"\n{DIVIDER}")
    print(f"  DEEP DIVE: {biz['name']}")
    print(DIVIDER)

    print(f"\n  Address:  {biz['address']}")
    if biz.get("phone"):
        print(f"  Phone:    {biz['phone']}")
    if biz.get("website"):
        print(f"  Website:  {biz['website']}")

    # Contact discovery results
    print(f"\n  {THIN_DIVIDER}")
    print("  TENANT / BUSINESS OWNER")
    print(f"  {THIN_DIVIDER}")

    if contacts.get("owner_name"):
        print(f"\n  >>> BUSINESS OWNER: {contacts['owner_name']} <<<")

    if contacts.get("emails"):
        print("\n  Emails found:")
        for email in contacts["emails"]:
            print(f"    - {email}")

    if contacts.get("phones"):
        print("\n  Phone numbers found:")
        for phone in contacts["phones"]:
            print(f"    - {phone}")

    if contacts.get("names"):
        print("\n  Other names (from website):")
        for name in contacts["names"]:
            print(f"    - {name}")

    if not any([contacts.get("owner_name"), contacts.get("emails"),
                contacts.get("phones"), contacts.get("names")]):
        print("\n  No tenant contact info found.")

    # Property ownership
    print(f"\n  {THIN_DIVIDER}")
    print("  PROPERTY OWNER / LANDLORD")
    print(f"  {THIN_DIVIDER}")

    if property_data:
        if property_data.get("property_owner"):
            print(f"\n  >>> PROPERTY OWNER: {property_data['property_owner']} <<<")
        else:
            print(f"\n  Property owner: not found via search")

        if property_data.get("zoning"):
            print(f"  Zoning: {property_data['zoning']}")

        if property_data.get("management_search"):
            print(f"\n  Management co. search: {property_data['management_search']}")

        # Direct lookup links — these are always useful
        print(f"\n  Quick lookups:")
        if property_data.get("loopnet_link"):
            print(f"    LoopNet:          {property_data['loopnet_link']}")
        if property_data.get("assessor_link"):
            print(f"    County assessor:  {property_data['assessor_link']}")
    else:
        print("\n  (Property lookup not run)")

    # Research links
    print(f"\n  {THIN_DIVIDER}")
    print("  RESEARCH LINKS")
    print(f"  {THIN_DIVIDER}")

    if links.get("owner_search"):
        print(f"\n  Tenant owner search:  {links['owner_search']}")
    if links.get("zoning_search"):
        print(f"  Zoning search:        {links['zoning_search']}")
    if links.get("property_search"):
        print(f"  Property owner search:{links['property_search']}")
    if links.get("county"):
        print(f"  County:               {links['county']}")
    if links.get("county_gis"):
        print(f"  County GIS:           {links['county_gis']}")

    print()


def export_csv(filepath, businesses, research_data=None):
    """Export results to CSV file."""
    fieldnames = [
        "name", "address", "phone", "website",
        "business_owner", "emails_found", "phones_found",
        "property_owner", "zoning",
        "management_search", "loopnet_link", "assessor_link",
        "county", "county_gis_link",
        "owner_search_link", "zoning_search_link", "property_search_link",
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
                row["business_owner"] = contacts.get("owner_name", "")
                row["emails_found"] = " | ".join(contacts.get("emails", []))
                row["phones_found"] = " | ".join(contacts.get("phones", []))
                row["property_owner"] = prop.get("property_owner", "")
                row["zoning"] = prop.get("zoning", "")
                row["management_search"] = prop.get("management_search", "")
                row["loopnet_link"] = prop.get("loopnet_link", "")
                row["assessor_link"] = prop.get("assessor_link", "")
                row["owner_search_link"] = links.get("owner_search", "")
                row["zoning_search_link"] = links.get("zoning_search", "")
                row["property_search_link"] = links.get("property_search", "")
                row["county"] = links.get("county", "")
                row["county_gis_link"] = links.get("county_gis", "")

            writer.writerow(row)

    print(f"\n  CSV saved to: {filepath}")
