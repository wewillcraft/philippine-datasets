#!/usr/bin/env python3

import json
import re
import os
from pathlib import Path
from ulid import ULID
import yaml
import toml
from collections import defaultdict
from typing import Dict, Set, Tuple

def parse_senator_name(full_name: str) -> Dict[str, any]:
    """Parse senator full name into components."""
    name_parts = {}
    aliases = []

    # Remove extra spaces
    clean_name = full_name.strip()

    # Check for nickname in quotes - add to aliases list
    nickname_matches = re.findall(r'"([^"]+)"', clean_name)
    for nickname in nickname_matches:
        aliases.append(nickname)
        clean_name = clean_name.replace(f'"{nickname}"', '').strip()

    if aliases:
        name_parts['aliases'] = aliases

    # Check for name prefix (Dr., Atty., etc.)
    prefix_match = re.match(r'^(Dr\.?|Atty\.?|Hon\.?|Rev\.?|Prof\.?|Engr\.?)\s+', clean_name, re.IGNORECASE)
    if prefix_match:
        name_parts['name_prefix'] = prefix_match.group(1).replace('.', '')
        clean_name = clean_name[len(prefix_match.group(0)):].strip()

    # Split by comma (Last, First format)
    if ',' in clean_name:
        parts = [p.strip() for p in clean_name.split(',', 1)]

        # Check if last name contains suffix (e.g., "Aquino IV")
        last_name = parts[0]
        last_suffix_match = re.search(r'\s+(Jr\.?|Sr\.?|III|II|IV|V|VI)\s*$', last_name)
        if last_suffix_match:
            name_parts['name_suffix'] = last_suffix_match.group(1).replace('.', '')
            last_name = last_name[:last_suffix_match.start()].strip()

        name_parts['last_name'] = last_name

        # Handle the rest (first name and middle initial)
        if len(parts) > 1:
            remaining = parts[1].strip()

            # Check for suffixes in the first name part
            suffix_match = re.search(r'\b(Jr\.?|Sr\.?|III|II|IV|V|VI)\b', remaining)
            if suffix_match and 'name_suffix' not in name_parts:
                name_parts['name_suffix'] = suffix_match.group(1).replace('.', '')
                remaining = remaining.replace(suffix_match.group(0), '').strip()

            # Split remaining into words
            words = remaining.split()
            if words:
                # Last word might be middle initial if it's a single letter
                if len(words) > 1 and len(words[-1]) <= 2 and words[-1].replace('.', '').isalpha():
                    name_parts['middle_initial'] = words[-1].replace('.', '')
                    name_parts['first_name'] = ' '.join(words[:-1])
                else:
                    name_parts['first_name'] = ' '.join(words)

    return name_parts

def load_existing_mappings(mapping_file: Path) -> Dict[str, str]:
    """Load existing code-to-ULID mappings from YAML file."""
    if mapping_file.exists():
        with open(mapping_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_mappings(mapping_file: Path, mappings: Dict[str, str]):
    """Save code-to-ULID mappings to YAML file."""
    # Sort mappings by key for consistent output
    sorted_mappings = dict(sorted(mappings.items()))
    with open(mapping_file, 'w') as f:
        yaml.dump(sorted_mappings, f, default_flow_style=False, sort_keys=False)

def normalize_senator_name(full_name: str) -> str:
    """Normalize senator name for comparison (remove quotes, extra spaces, etc.)"""
    # Remove quotes and extra spaces
    normalized = re.sub(r'"[^"]*"', '', full_name).strip()
    # Remove extra spaces
    normalized = ' '.join(normalized.split())
    return normalized

def normalize_committee_name(name: str) -> str:
    """Normalize committee name for comparison."""
    # Remove extra spaces and normalize
    normalized = ' '.join(name.split())
    # Remove common variations
    normalized = normalized.replace("Cong. ", "Congressional ")
    normalized = normalized.replace("Jt. ", "Joint ")
    return normalized.lower()

def extract_senators_and_committees(json_file: Path):
    """Extract unique senators and committees from the JSON file."""
    with open(json_file, 'r') as f:
        data = json.load(f)

    # Data structures for unique senators and committees
    all_senators = {}  # code -> senator data
    senator_congresses = defaultdict(set)  # code -> set of congress numbers
    all_committees = {}  # code -> committee data
    committee_congresses = defaultdict(set)  # code -> set of congress numbers

    # Extract from each congress
    for congress_num, congress_data in data['congresses'].items():
        congress_num = int(congress_num)

        # Extract senators
        if 'senators' in congress_data:
            for senator_code, senator_data in congress_data['senators'].items():
                if senator_code not in all_senators:
                    all_senators[senator_code] = senator_data
                senator_congresses[senator_code].add(congress_num)

        # Extract committees
        if 'committees' in congress_data:
            for committee_code, committee_data in congress_data['committees'].items():
                if committee_code not in all_committees:
                    all_committees[committee_code] = committee_data
                committee_congresses[committee_code].add(congress_num)

    # Group senators by normalized name to find duplicates
    senator_groups = defaultdict(list)  # normalized_name -> [(code, data)]
    for code, data in all_senators.items():
        normalized = normalize_senator_name(data['full_name'])
        senator_groups[normalized].append((code, data))

    # Merge duplicate senators
    unique_senators = {}  # primary_code -> {data, all_codes, all_congresses}
    for normalized_name, senator_list in senator_groups.items():
        if len(senator_list) > 1:
            # Multiple codes for same person - merge them
            primary_code = sorted([code for code, _ in senator_list])[0]  # Use first code alphabetically
            all_codes = [code for code, _ in senator_list]
            all_congresses = set()
            for code, _ in senator_list:
                all_congresses.update(senator_congresses[code])

            # Use the first senator's data
            unique_senators[primary_code] = {
                'data': senator_list[0][1],
                'codes': all_codes,
                'congresses': all_congresses
            }
        else:
            # Single code for this person
            code, data = senator_list[0]
            unique_senators[code] = {
                'data': data,
                'codes': [code],
                'congresses': senator_congresses[code]
            }

    # Group committees by normalized name to find duplicates
    committee_groups = defaultdict(list)  # normalized_name -> [(code, data)]
    for code, data in all_committees.items():
        normalized = normalize_committee_name(data['name'])
        committee_groups[normalized].append((code, data))

    # Merge duplicate committees
    unique_committees = {}  # primary_code -> {data, all_codes, all_congresses}
    for normalized_name, committee_list in committee_groups.items():
        if len(committee_list) > 1:
            # Multiple codes for same committee - merge them
            primary_code = sorted([code for code, _ in committee_list])[0]  # Use first code alphabetically
            all_codes = [code for code, _ in committee_list]
            all_congresses = set()
            for code, _ in committee_list:
                all_congresses.update(committee_congresses[code])

            # Use the first committee's data
            unique_committees[primary_code] = {
                'data': committee_list[0][1],
                'codes': all_codes,
                'congresses': all_congresses
            }
        else:
            # Single code for this committee
            code, data = committee_list[0]
            unique_committees[code] = {
                'data': data,
                'codes': [code],
                'congresses': committee_congresses[code]
            }

    return unique_senators, unique_committees

def main():
    # Setup paths
    base_dir = Path(__file__).parent
    json_file = base_dir / 'metadata' / 'all_congresses.json'
    people_dir = base_dir / 'people'
    committees_dir = base_dir / 'committees'

    # Create directories if they don't exist
    people_dir.mkdir(exist_ok=True)
    committees_dir.mkdir(exist_ok=True)

    # Load existing mappings
    senate_mapping_file = people_dir / 'senate-website-key-mapping.yml'
    committee_mapping_file = committees_dir / 'senate-website-key-mapping.yml'

    senate_mappings = load_existing_mappings(senate_mapping_file)
    committee_mappings = load_existing_mappings(committee_mapping_file)

    # Extract data
    print("Extracting senators and committees...")
    unique_senators, unique_committees = extract_senators_and_committees(json_file)

    # Process senators
    print(f"\nProcessing {len(unique_senators)} unique senators...")

    # First pass: ensure all senator codes have mappings
    for primary_code, senator_info in sorted(unique_senators.items()):
        # For senators with multiple codes, map all codes to the same ULID
        if primary_code not in senate_mappings:
            ulid = str(ULID())
            for code in senator_info['codes']:
                senate_mappings[code] = ulid
        else:
            # Ensure all codes map to the same ULID
            ulid = senate_mappings[primary_code]
            for code in senator_info['codes']:
                senate_mappings[code] = ulid

    # Track which ULIDs we've already processed
    processed_ulids = set()

    for primary_code, senator_info in sorted(unique_senators.items()):
        ulid = senate_mappings[primary_code]

        # Skip if we've already processed this ULID (for duplicate codes)
        if ulid in processed_ulids:
            continue
        processed_ulids.add(ulid)

        # Parse name
        name_parts = parse_senator_name(senator_info['data']['full_name'])

        # Prepare TOML data with senate_website_keys as an array
        toml_data = {
            'id': ulid,
            'senate_website_keys': sorted(senator_info['codes']),  # Array of all codes
            'full_name': senator_info['data']['full_name'],
            **name_parts,
            'congresses': sorted(list(senator_info['congresses']))
        }

        # Write TOML file
        toml_file = people_dir / f"{ulid}.toml"
        with open(toml_file, 'w') as f:
            toml.dump(toml_data, f)

    # Process committees
    print(f"\nProcessing {len(unique_committees)} unique committees...")

    # First pass: ensure all committee codes have mappings
    for primary_code, committee_info in sorted(unique_committees.items()):
        # For committees with multiple codes, map all codes to the same ULID
        if primary_code not in committee_mappings:
            ulid = str(ULID())
            for code in committee_info['codes']:
                committee_mappings[code] = ulid
        else:
            # Ensure all codes map to the same ULID
            ulid = committee_mappings[primary_code]
            for code in committee_info['codes']:
                committee_mappings[code] = ulid

    # Track which ULIDs we've already processed
    processed_committee_ulids = set()

    for primary_code, committee_info in sorted(unique_committees.items()):
        ulid = committee_mappings[primary_code]

        # Skip if we've already processed this ULID (for duplicate codes)
        if ulid in processed_committee_ulids:
            continue
        processed_committee_ulids.add(ulid)

        # Prepare TOML data with senate_website_keys as an array
        toml_data = {
            'id': ulid,
            'senate_website_keys': sorted(committee_info['codes']),  # Array of all codes
            'name': committee_info['data']['name'],
            'type': committee_info['data'].get('type', 'regular'),
            'congresses': sorted(list(committee_info['congresses']))
        }

        # Write TOML file
        toml_file = committees_dir / f"{ulid}.toml"
        with open(toml_file, 'w') as f:
            toml.dump(toml_data, f)

    # Save mappings
    print("\nSaving mappings...")
    save_mappings(senate_mapping_file, senate_mappings)
    save_mappings(committee_mapping_file, committee_mappings)

    # Count unique files (unique ULIDs)
    unique_senator_ulids = len(set(senate_mappings.values()))
    unique_committee_ulids = len(set(committee_mappings.values()))

    print(f"\nDone!")
    print(f"- Created {unique_senator_ulids} unique senator files in {people_dir}")
    print(f"- Created {unique_committee_ulids} unique committee files in {committees_dir}")
    print(f"- Senate mapping saved to {senate_mapping_file} ({len(senate_mappings)} codes)")
    print(f"- Committee mapping saved to {committee_mapping_file} ({len(committee_mappings)} codes)")

if __name__ == "__main__":
    main()