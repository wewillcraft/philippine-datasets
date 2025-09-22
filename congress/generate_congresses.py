#!/usr/bin/env python3

from pathlib import Path
from ulid import ULID
import yaml
import toml

# Congress data with website keys and year ranges
CONGRESS_DATA = {
    8: {
        'congress_website_key': 8,
        'ordinal': '8th',
        'start_date': '1987-07-27',
        'end_date': '1992-06-17',
        'start_year': 1987,
        'end_year': 1992,
    },
    9: {
        'congress_website_key': 9,
        'ordinal': '9th',
        'start_date': '1992-07-27',
        'end_date': '1995-06-09',
        'start_year': 1992,
        'end_year': 1995,
    },
    10: {
        'congress_website_key': 10,
        'ordinal': '10th',
        'start_date': '1995-07-24',
        'end_date': '1998-06-05',
        'start_year': 1995,
        'end_year': 1998,
    },
    11: {
        'congress_website_key': 11,
        'ordinal': '11th',
        'start_date': '1998-07-27',
        'end_date': '2001-06-08',
        'start_year': 1998,
        'end_year': 2001,
    },
    12: {
        'congress_website_key': 12,
        'ordinal': '12th',
        'start_date': '2001-06-30',
        'end_date': '2004-06-30',
        'start_year': 2001,
        'end_year': 2004,
    },
    13: {
        'congress_website_key': 13,
        'ordinal': '13th',
        'start_date': '2004-07-26',
        'end_date': '2007-06-08',
        'start_year': 2004,
        'end_year': 2007,
    },
    14: {
        'congress_website_key': 14,
        'ordinal': '14th',
        'start_date': '2007-07-23',
        'end_date': '2010-06-09',
        'start_year': 2007,
        'end_year': 2010,
    },
    15: {
        'congress_website_key': 15,
        'ordinal': '15th',
        'start_date': '2010-07-26',
        'end_date': '2013-06-06',
        'start_year': 2010,
        'end_year': 2013,
    },
    16: {
        'congress_website_key': 16,
        'ordinal': '16th',
        'start_date': '2013-07-22',
        'end_date': '2016-06-06',
        'start_year': 2013,
        'end_year': 2016,
    },
    17: {
        'congress_website_key': 17,
        'ordinal': '17th',
        'start_date': '2016-07-25',
        'end_date': '2019-06-04',
        'start_year': 2016,
        'end_year': 2019,
    },
    18: {
        'congress_website_key': 18,
        'ordinal': '18th',
        'start_date': '2019-07-22',
        'end_date': '2022-06-01',
        'start_year': 2019,
        'end_year': 2022,
    },
    19: {
        'congress_website_key': 19,
        'ordinal': '19th',
        'start_date': '2022-07-25',
        'end_date': '2025-06-11',
        'start_year': 2022,
        'end_year': 2025,
    },
    20: {
        'congress_website_key': 103,  # Special mapping for 20th congress
        'ordinal': '20th',
        'start_date': '2025-07-28',
        'end_date': None,  # Current congress, no end date yet
        'start_year': 2025,
        'end_year': None,  # Will be 2028 presumably
    },
}

def load_existing_mappings(mapping_file: Path) -> dict:
    """Load existing congress-to-ULID mappings from YAML file."""
    if mapping_file.exists():
        with open(mapping_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_mappings(mapping_file: Path, mappings: dict):
    """Save congress-to-ULID mappings to YAML file."""
    # Sort mappings by key for consistent output
    sorted_mappings = dict(sorted(mappings.items(), key=lambda x: x[0]))
    with open(mapping_file, 'w') as f:
        yaml.dump(sorted_mappings, f, default_flow_style=False, sort_keys=False)

def main():
    # Setup paths
    base_dir = Path(__file__).parent
    congresses_dir = base_dir / 'congresses'

    # Create directory if it doesn't exist
    congresses_dir.mkdir(exist_ok=True)

    # Load existing mappings
    mapping_file = congresses_dir / 'congress-number-mapping.yml'
    congress_mappings = load_existing_mappings(mapping_file)

    print(f"Generating Congress TOML files...")

    # Process all congresses in sorted order to ensure consistent ULID generation
    # First, generate ULIDs for any new congresses in order
    for congress_num in sorted(CONGRESS_DATA.keys()):
        if congress_num not in congress_mappings:
            congress_mappings[congress_num] = str(ULID())

    # Now process each congress in order
    for congress_num in sorted(CONGRESS_DATA.keys()):
        congress_info = CONGRESS_DATA[congress_num]
        ulid = congress_mappings[congress_num]

        # Prepare TOML data
        toml_data = {
            'id': ulid,
            'congress_number': congress_num,
            'congress_website_keys': [congress_info['congress_website_key']],  # Array for consistency
            'ordinal': congress_info['ordinal'],
            'name': f"{congress_info['ordinal']} Congress of the Philippines",
            'start_date': congress_info['start_date'],
            'start_year': congress_info['start_year'],
        }

        # Add end date and year if available
        if congress_info['end_date']:
            toml_data['end_date'] = congress_info['end_date']
        if congress_info['end_year']:
            toml_data['end_year'] = congress_info['end_year']

        # Add year range
        if congress_info['end_year']:
            toml_data['year_range'] = f"{congress_info['start_year']}-{congress_info['end_year']}"
        else:
            toml_data['year_range'] = f"{congress_info['start_year']}-present"

        # Write TOML file
        toml_file = congresses_dir / f"{ulid}.toml"
        with open(toml_file, 'w') as f:
            toml.dump(toml_data, f)

        print(f"  - Created {congress_info['ordinal']} Congress ({toml_data['year_range']})")

    # Save mappings
    print("\nSaving congress mapping...")
    save_mappings(mapping_file, congress_mappings)

    print(f"\nDone!")
    print(f"- Created {len(congress_mappings)} congress files in {congresses_dir}")
    print(f"- Congress mapping saved to {mapping_file}")

if __name__ == "__main__":
    main()