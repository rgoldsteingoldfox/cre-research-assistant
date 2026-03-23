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


def print_deep_dive(biz, contacts, links):
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
    print("  CONTACT DISCOVERY")
    print(f"  {THIN_DIVIDER}")

    if contacts.get("owner_name"):
        print(f"\n  >>> OWNER: {contacts['owner_name']} <<<")

    if contacts.get("owner_snippets"):
        print("\n  Search snippets:")
        for snippet in contacts["owner_snippets"]:
            print(f"    - {snippet}")

    if contacts.get("emails"):
        print("\n  Emails found:")
        for email in contacts["emails"]:
            print(f"    - {email}")

    if contacts.get("phones"):
        print("\n  Phone numbers found:")
        for phone in contacts["phones"]:
            print(f"    - {phone}")

    if contacts.get("names"):
        print("\n  Possible owner names (from website):")
        for name in contacts["names"]:
            print(f"    - {name}")

    if not any([contacts.get("owner_snippets"), contacts.get("emails"),
                contacts.get("phones"), contacts.get("names")]):
        print("\n  No additional contacts found.")

    # Research links
    print(f"\n  {THIN_DIVIDER}")
    print("  RESEARCH LINKS")
    print(f"  {THIN_DIVIDER}")

    if links.get("owner_search"):
        print(f"\n  Owner search:    {links['owner_search']}")
    if links.get("zoning_search"):
        print(f"  Zoning search:   {links['zoning_search']}")
    if links.get("property_search"):
        print(f"  Property search: {links['property_search']}")
    if links.get("county"):
        print(f"  County:          {links['county']}")
    if links.get("county_gis"):
        print(f"  County GIS:      {links['county_gis']}")

    print()


def export_csv(filepath, businesses, research_data=None):
    """Export results to CSV file."""
    fieldnames = [
        "name", "address", "phone", "website", "owner_name",
        "owner_snippets", "emails_found", "phones_found", "names_found",
        "owner_search_link", "zoning_search_link", "property_search_link",
        "county", "county_gis_link",
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
                row["owner_name"] = contacts.get("owner_name", "")
                row["owner_snippets"] = " | ".join(contacts.get("owner_snippets", []))
                row["emails_found"] = " | ".join(contacts.get("emails", []))
                row["phones_found"] = " | ".join(contacts.get("phones", []))
                row["names_found"] = " | ".join(contacts.get("names", []))
                row["owner_search_link"] = links.get("owner_search", "")
                row["zoning_search_link"] = links.get("zoning_search", "")
                row["property_search_link"] = links.get("property_search", "")
                row["county"] = links.get("county", "")
                row["county_gis_link"] = links.get("county_gis", "")

            writer.writerow(row)

    print(f"\n  CSV saved to: {filepath}")
