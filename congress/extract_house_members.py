#!/usr/bin/env python3

import re
import os
from pathlib import Path
from ulid import ULID
import yaml
import toml
from collections import defaultdict
from typing import Dict, List, Set

def parse_member_name(full_name: str) -> Dict[str, any]:
    """Parse House member full name into components."""
    name_parts = {}

    # Clean up the full name - remove leading/trailing whitespace and commas
    clean_name = full_name.strip().strip(',')

    # Split by comma to get last name and rest
    if ',' in clean_name:
        parts = [p.strip() for p in clean_name.split(',', 1)]
        last_name = parts[0].strip()

        # Store last name (convert to title case for consistency)
        name_parts['last_name'] = last_name.title()

        # Parse first and middle name from the rest
        if len(parts) > 1:
            rest = parts[1].strip()

            # Split the rest into words
            words = rest.split()
            if words:
                # First word is the first name
                name_parts['first_name'] = words[0].title()

                # If there are more words, they're middle names/initials
                if len(words) > 1:
                    middle_parts = words[1:]
                    # Join all middle parts
                    middle = ' '.join(middle_parts)
                    # Remove periods from initials
                    middle = middle.replace('.', '')
                    name_parts['middle_name'] = middle.title()

    return name_parts

def extract_congresses_from_file(file_path: Path) -> Set[int]:
    """Extract congress numbers from a House member file."""
    congresses = set()

    with open(file_path, 'r') as f:
        data = toml.load(f)

    # Check for memberships array (newer format)
    if 'memberships' in data:
        for membership in data['memberships']:
            if 'congress' in membership:
                congresses.add(membership['congress'])

    # Check for principalAuthoredBills array (older format)
    if 'principalAuthoredBills' in data:
        for bill_group in data['principalAuthoredBills']:
            if 'congress' in bill_group:
                congresses.add(bill_group['congress'])

    return congresses

def load_existing_mappings(mapping_file: Path) -> Dict[str, str]:
    """Load existing author ID to ULID mappings from YAML file."""
    if mapping_file.exists():
        with open(mapping_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_mappings(mapping_file: Path, mappings: Dict[str, str]):
    """Save author ID to ULID mappings to YAML file."""
    # Sort mappings by key for consistent output
    sorted_mappings = dict(sorted(mappings.items()))
    with open(mapping_file, 'w') as f:
        yaml.dump(sorted_mappings, f, default_flow_style=False, sort_keys=False)

def normalize_name_for_comparison(full_name: str) -> str:
    """Normalize a name for comparison purposes."""
    # Remove all non-alphanumeric characters and convert to lowercase
    normalized = re.sub(r'[^a-zA-Z0-9]', '', full_name).lower()
    return normalized

def main():
    # Setup paths
    base_dir = Path(__file__).parent
    input_dir = base_dir / 'house' / 'members' / 'all'
    output_dir = base_dir / 'house' / 'members' / 'person'

    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing mappings
    mapping_file = output_dir / 'house-website-key-mapping.yml'
    author_mappings = load_existing_mappings(mapping_file)

    # Dictionary to group members by normalized name
    member_groups = defaultdict(list)  # normalized_name -> [(author_id, id, file_path)]

    # First pass: read all files and group by normalized name
    print("Reading House member files...")
    for file_path in sorted(input_dir.glob('*.toml')):
        with open(file_path, 'r') as f:
            data = toml.load(f)

        author_id = data.get('authorId')
        member_id = data.get('id')
        full_name = data.get('fullName', '')

        if author_id and full_name:
            normalized = normalize_name_for_comparison(full_name)
            member_groups[normalized].append((author_id, member_id, file_path))

    print(f"Found {len(member_groups)} unique members")

    # Process each unique member
    processed_ulids = set()

    for normalized_name, member_list in sorted(member_groups.items()):
        # Get or create ULID for this person
        primary_author_id = sorted([author_id for author_id, _, _ in member_list])[0]

        if primary_author_id not in author_mappings:
            ulid = str(ULID())
            # Map all author IDs for this person to the same ULID
            for author_id, _, _ in member_list:
                author_mappings[author_id] = ulid
        else:
            ulid = author_mappings[primary_author_id]
            # Ensure all author IDs map to the same ULID
            for author_id, _, _ in member_list:
                author_mappings[author_id] = ulid

        # Skip if we've already processed this ULID
        if ulid in processed_ulids:
            continue
        processed_ulids.add(ulid)

        # Collect all congress IDs and author IDs for this person
        all_congress_ids = []
        all_author_ids = []
        all_congresses = set()

        # Use the first file's data as the primary source
        primary_file = member_list[0][2]
        with open(primary_file, 'r') as f:
            primary_data = toml.load(f)

        for author_id, member_id, file_path in member_list:
            all_author_ids.append(author_id)
            if member_id:
                all_congress_ids.append(member_id)

            # Extract congresses from this file
            congresses = extract_congresses_from_file(file_path)
            all_congresses.update(congresses)

        # Parse name components
        full_name = primary_data.get('fullName', '')
        name_parts = parse_member_name(full_name)

        # Get nickname/aliases
        aliases = []
        nick_name = primary_data.get('nickName', '').strip()
        if nick_name and nick_name != full_name:
            # Clean up the nickname - remove "HON." prefix if present
            nick_name = re.sub(r'^HON\.\s*', '', nick_name, flags=re.IGNORECASE).strip()
            # Only add if it's different from the parsed names
            if nick_name and nick_name not in [name_parts.get('first_name', ''), full_name]:
                # Extract just the nickname part if it contains the full name
                # For example: "JERNIE JETT V. NISAY" -> we want "JERNIE JETT"
                if name_parts.get('first_name'):
                    # Check if nickname contains first name
                    first_name = name_parts['first_name']
                    if first_name in nick_name:
                        # Extract the actual nickname part
                        words = nick_name.split()
                        # Keep words until we hit the last name
                        nickname_parts = []
                        for word in words:
                            if word.upper() == name_parts.get('last_name', '').upper():
                                break
                            nickname_parts.append(word)
                        if nickname_parts:
                            actual_nickname = ' '.join(nickname_parts).title()
                            if actual_nickname != first_name:
                                aliases.append(actual_nickname)
                    else:
                        aliases.append(nick_name.title())

        # Create the person TOML data
        person_data = {
            'id': ulid,
            'congress_website_primary_keys': sorted(all_congress_ids),
            'congress_website_author_keys': sorted(all_author_ids),
            'full_name': full_name
        }

        # Add name parts
        if 'last_name' in name_parts:
            person_data['last_name'] = name_parts['last_name']
        if 'first_name' in name_parts:
            person_data['first_name'] = name_parts['first_name']
        if 'middle_name' in name_parts:
            person_data['middle_name'] = name_parts['middle_name']

        # Add aliases if present
        if aliases:
            person_data['aliases'] = aliases

        # Add congresses
        if all_congresses:
            person_data['congresses'] = sorted(list(all_congresses))

        # Write the person TOML file
        output_file = output_dir / f"{ulid}.toml"
        with open(output_file, 'w') as f:
            toml.dump(person_data, f)

    # Save mappings
    print("Saving mappings...")
    save_mappings(mapping_file, author_mappings)

    # Count unique files
    unique_member_ulids = len(processed_ulids)

    print(f"\nDone!")
    print(f"- Created {unique_member_ulids} unique House member files in {output_dir}")
    print(f"- Mapping saved to {mapping_file} ({len(author_mappings)} author IDs)")

if __name__ == "__main__":
    main()