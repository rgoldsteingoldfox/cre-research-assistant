#!/usr/bin/env python3
"""
CRE Research Assistant — Help commercial real estate brokers find tenant
businesses, identify owners/contacts, and look up zoning/property data.

Usage:
    python3 cre.py                                                          # Interactive mode
    python3 cre.py --type "coffee shops" --location "Roswell, GA"           # Non-interactive
    python3 cre.py --type "coffee shops" --location "Roswell, GA" --all     # Research all
    python3 cre.py --type "coffee shops" --location "Roswell, GA" --all --csv output.csv
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


def main():
    parser = argparse.ArgumentParser(description="CRE Research Assistant")
    parser.add_argument("--csv", help="Export results to CSV file", metavar="FILE")
    parser.add_argument("--all", action="store_true", help="Research all results automatically")
    parser.add_argument("--type", help="Business type (e.g., 'coffee shops')", metavar="TYPE")
    parser.add_argument("--location", help="Location (e.g., 'Roswell, GA')", metavar="LOC")
    args = parser.parse_args()

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
