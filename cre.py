#!/usr/bin/env python3
"""
CRE Research Assistant — Help commercial real estate brokers find tenant
businesses, identify owners/contacts, and look up zoning/property data.

Usage:
  Tenant research mode (find businesses + owners):
    python3 cre.py --type "coffee shops" --location "Roswell, GA" --all --csv output.csv

  Property lookup mode (feed addresses, get owner + zoning):
    python3 cre.py --addresses addresses.txt --csv output.csv
    python3 cre.py --addresses "1090 Alpharetta St, Roswell, GA; 585 Atlanta St, Roswell, GA"
"""

import os
import sys
import argparse
import time

# Add project root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from skills.find_businesses import search_businesses
from skills.contact_discovery import research_business
from skills.research_links import generate_links
from skills.property_lookup import lookup_property
from utils.output import print_header, print_business_list, print_deep_dive, export_csv


def deep_dive(biz, city):
    """Run full contact discovery + research links for one business."""
    print(f"\n  Researching {biz['name']}...")

    contacts = research_business(
        business_name=biz["name"],
        city=city,
        website=biz.get("website"),
    )

    links = generate_links(
        business_name=biz["name"],
        address=biz["address"],
        city=city,
    )

    print(f"  Looking up property owner...")
    property_data = lookup_property(biz["address"])

    print_deep_dive(biz, contacts, links, property_data)
    return {"contacts": contacts, "links": links, "property": property_data}


def interactive_mode(businesses, city):
    """Let user select businesses to deep-dive on."""
    research_data = {}

    while True:
        print(f"\n  Enter a number (1-{len(businesses)}) to deep-dive on a business.")
        print("  Type 'list' to see the list again.")
        print("  Type 'all' to research all businesses.")
        print("  Type 'quit' to exit.\n")

        choice = input("  > ").strip().lower()

        if choice in ("q", "quit", "exit"):
            break
        elif choice == "list":
            print_business_list(businesses)
        elif choice == "all":
            for biz in businesses:
                data = deep_dive(biz, city)
                research_data[biz["name"]] = data
                time.sleep(0.5)
        else:
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(businesses):
                    biz = businesses[idx]
                    data = deep_dive(biz, city)
                    research_data[biz["name"]] = data
                else:
                    print(f"  Please enter a number between 1 and {len(businesses)}")
            except ValueError:
                print("  Invalid input. Enter a number, 'list', 'all', or 'quit'.")

    return research_data


def property_lookup_mode(addresses, csv_path=None, generate_reports=False):
    """Look up property owner + zoning for a list of addresses."""
    from utils.output import DIVIDER, THIN_DIVIDER
    import csv

    print_header("PROPERTY LOOKUP MODE")
    print(f"\n  Looking up {len(addresses)} addresses...\n")

    results = []
    for i, addr in enumerate(addresses):
        addr = addr.strip()
        if not addr:
            continue

        print(f"  [{i+1}/{len(addresses)}] {addr}...", end=" ", flush=True)
        prop = lookup_property(addr)

        owner = prop.get("property_owner", "")
        zoning = prop.get("zoning", "")
        zoning_uses = prop.get("zoning_uses", "")
        parcel = prop.get("parcel_id", "")
        source = prop.get("data_source", "")

        # Flatten LLC details for CSV export
        llc = prop.get("llc_details", {})
        prop["llc_person"] = llc.get("person_name", "")
        prop["llc_registered_agent"] = llc.get("registered_agent", "")
        prop["llc_principal_address"] = llc.get("principal_address", "")
        prop["llc_phone"] = llc.get("phone", "")
        prop["llc_email"] = llc.get("email", "")
        prop["llc_linkedin"] = llc.get("linkedin", "")
        prop["llc_filing_status"] = llc.get("filing_status", "")

        results.append({"address": addr, **prop})

        if owner or zoning:
            print(f"Owner: {owner or '?'} | Zone: {zoning or '?'} [{source}]")
        else:
            print("no data found")

    # Print summary
    print(f"\n{DIVIDER}")
    print(f"  RESULTS")
    print(DIVIDER)

    for r in results:
        addr = r["address"]
        owner = r.get("property_owner", "")
        zoning = r.get("zoning", "")
        zoning_uses = r.get("zoning_uses", "")
        parcel = r.get("parcel_id", "")

        print(f"\n  {addr}")
        print(f"  {THIN_DIVIDER}")
        if owner:
            print(f"  Property Owner: {owner}")
        mail_addr = r.get("owner_mail_address", "")
        if mail_addr:
            print(f"  Tax Mailing:    {mail_addr}")
        if zoning:
            print(f"  Zoning:         {zoning}")
        if zoning_uses:
            print(f"  {zoning_uses}")
        if parcel:
            print(f"  Parcel ID:      {parcel}")
        if r.get("management_search"):
            print(f"  Owner search:   {r['management_search']}")
        # LLC details
        llc = r.get("llc_details", {})
        if llc and (llc.get("person_name") or llc.get("registered_agent")):
            print(f"  --- Person Behind LLC ---")
            if llc.get("person_name"):
                print(f"  Person:           {llc['person_name']}")
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

        if r.get("qpublic_link"):
            print(f"  qPublic (owner):  {r['qpublic_link']}")
        if r.get("ga_sos_link"):
            print(f"  GA SOS (LLC):     {r['ga_sos_link']}")
        if r.get("gsccca_link"):
            print(f"  GSCCCA (deeds):   {r['gsccca_link']}")
        if not owner and not zoning:
            print(f"  No data found — try the county assessor:")
            if r.get("assessor_link"):
                print(f"  {r['assessor_link']}")

    # CSV export
    if csv_path:
        fieldnames = [
            "address", "property_owner", "owner_mail_address",
            "zoning", "zoning_uses", "parcel_id",
            "llc_person", "llc_registered_agent", "llc_principal_address",
            "llc_phone", "llc_email", "llc_linkedin", "llc_filing_status",
            "data_source", "management_search", "loopnet_link", "assessor_link",
            "qpublic_link", "ga_sos_link", "gsccca_link",
        ]
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in results:
                writer.writerow(r)
        print(f"\n  CSV saved to: {csv_path}")

    # PDF report generation
    if generate_reports:
        from utils.report import generate_report
        report_dir = os.path.join(os.path.dirname(__file__), "reports")
        print(f"\n  Generating PDF reports...")
        for r in results:
            filepath = generate_report(r, r["address"], output_dir=report_dir)
            print(f"  Report saved: {filepath}")

    found = sum(1 for r in results if r.get("property_owner"))
    zoned = sum(1 for r in results if r.get("zoning"))
    print(f"\n{DIVIDER}")
    print(f"  {len(results)} addresses | {found} owners found | {zoned} zoning found")
    print(DIVIDER)


def main():
    parser = argparse.ArgumentParser(description="CRE Research Assistant")
    parser.add_argument("--csv", help="Export results to CSV file", metavar="FILE")
    parser.add_argument("--all", action="store_true", help="Research all results automatically")
    parser.add_argument("--type", help="Business type (e.g., 'coffee shops')", metavar="TYPE")
    parser.add_argument("--location", help="Location (e.g., 'Roswell, GA')", metavar="LOC")
    parser.add_argument("--addresses", help="Property lookup mode: file path or semicolon-separated addresses", metavar="ADDRS")
    parser.add_argument("--report", action="store_true", help="Generate PDF report for each property")
    args = parser.parse_args()

    # === Property Lookup Mode ===
    if args.addresses:
        # Check if it's a file path or inline addresses
        if os.path.isfile(args.addresses):
            with open(args.addresses, "r") as f:
                addresses = [line.strip() for line in f if line.strip()]
        else:
            addresses = [a.strip() for a in args.addresses.split(";") if a.strip()]

        if not addresses:
            print("  No addresses found. Exiting.")
            return

        property_lookup_mode(addresses, args.csv, args.report)
        return

    # === Tenant Research Mode ===
    print_header("CRE RESEARCH ASSISTANT")
    print()

    # Get user input — from flags or interactive prompts
    business_type = args.type
    if not business_type:
        business_type = input("  Business type (e.g., coffee shops): ").strip()
    if not business_type:
        print("  No business type entered. Exiting.")
        return

    location = args.location
    if not location:
        location = input("  Location (e.g., Roswell, GA): ").strip()
    if not location:
        print("  No location entered. Exiting.")
        return

    # Extract city for later use
    city = location.split(",")[0].strip()

    # Step 1: Find businesses
    print()
    businesses = search_businesses(business_type, location)

    if not businesses:
        print("\n  No businesses found. Try a different search.")
        return

    # Step 2: Display results
    print_business_list(businesses)

    # Step 3: Research
    research_data = {}

    if args.all:
        # Auto-research all businesses
        print_header("RESEARCHING ALL BUSINESSES")
        for biz in businesses:
            data = deep_dive(biz, city)
            research_data[biz["name"]] = data
            time.sleep(0.5)
    else:
        # Interactive mode
        research_data = interactive_mode(businesses, city)

    # Step 4: CSV export
    if args.csv:
        export_csv(args.csv, businesses, research_data)

    print_header("DONE")
    print(f"\n  Found {len(businesses)} businesses.")
    if research_data:
        print(f"  Deep-dived on {len(research_data)} businesses.")
    if args.csv:
        print(f"  Results saved to {args.csv}")
    print()


if __name__ == "__main__":
    main()
