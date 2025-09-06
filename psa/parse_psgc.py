#!/usr/bin/env python3
"""
Parse and clean PSGC (Philippine Standard Geographic Code) data from Excel file.
"""

import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Any, Optional


def clean_value(value: Any) -> Any:
    """Clean individual cell values."""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def validate_correspondence_code(code: Any) -> tuple[Optional[str], bool]:
    """
    Validate and clean correspondence code.
    Returns tuple of (cleaned_code, has_warning)
    
    Valid codes should be integers represented as floats ending in .0
    (e.g., '130000000.0' -> '130000000')
    
    Warns if code has non-zero decimal part (e.g., '130000000.2')
    """
    if code is None or pd.isna(code):
        return None, False
    
    code_str = str(code).strip()
    
    # Check if it's a float-like string
    if '.' in code_str:
        try:
            float_val = float(code_str)
            # Check if decimal part is .0
            if float_val == int(float_val):
                # Valid integer representation, remove .0
                return str(int(float_val)), False
            else:
                # Non-zero decimal part - this is problematic
                return code_str, True
        except ValueError:
            # Not a valid number
            return code_str, False
    
    # No decimal point, return as is
    return code_str, False


def parse_psgc_code(code: str) -> Dict[str, Optional[str]]:
    """
    Parse a 10-digit PSGC code into its components.
    Format: RRPPPMMBBB
    RR - Region code (01-19)
    PPP - Province code/HUC
    LL - Locality (Municipality/City) code
    BBB - Barangay code
    """
    if not code or len(code) != 10:
        return {
            'region': None,
            'province': None,
            'municipality': None,
            'barangay': None
        }
    
    return {
        'region': code[:2],
        'province': code[2:5],
        'municipality': code[5:7],
        'barangay': code[7:10]
    }


def determine_admin_level(geo_level: str, psgc_parts: Dict[str, str], name: str = '') -> str:
    """Determine the administrative level based on geographic level and PSGC code."""
    # Handle pandas NA/NaN values
    if pd.isna(geo_level):
        geo_level = None
        
    geo_level_lower = str(geo_level).lower() if geo_level else ''
    
    # Special cases for entries with null geographic level
    if not geo_level:
        # City of Isabela (Not a Province) - explicitly not a province
        if 'not a province' in name.lower():
            return 'city_municipality'
        # Special Geographic Area
        elif 'special geographic area' in name.lower():
            return 'special_area'
    
    # Check for SubMun BEFORE checking for Mun to avoid false matches
    if 'submun' in geo_level_lower:
        return 'sub_municipality'
    elif 'reg' in geo_level_lower:
        return 'region'
    elif 'prov' in geo_level_lower:
        return 'province'
    elif 'city' in geo_level_lower or 'mun' in geo_level_lower:
        return 'city_municipality'
    elif 'bgy' in geo_level_lower or 'brgy' in geo_level_lower or 'barangay' in geo_level_lower:
        return 'barangay'
    elif 'dist' in geo_level_lower:
        return 'district'
    
    # Fallback: determine by PSGC code structure
    if psgc_parts['barangay'] != '000':
        return 'barangay'
    elif psgc_parts['municipality'] != '00':
        return 'city_municipality'
    elif psgc_parts['province'] != '000':
        return 'province'
    elif psgc_parts['region'] != '00':
        return 'region'
    
    return 'unknown'


def process_psgc_data(file_path: str, sheet_name: str = 'PSGC') -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Process the PSGC Excel file and return cleaned data.
    Returns tuple of (processed_data, validation_warnings)
    """
    print(f"Reading Excel file: {file_path}")
    # Read Excel with PSGC code as string to preserve leading zeros
    df = pd.read_excel(file_path, sheet_name=sheet_name, dtype={0: str})
    print(f"Loaded {len(df)} rows from Excel")
    
    # Rename columns based on the provided mapping
    column_mapping = {
        df.columns[0]: 'psgc_code',  # A: "10-digit PSGC"
        df.columns[1]: 'name',  # B: "Name"
        df.columns[2]: 'correspondence_code',  # C: "Correspondence Code"
        df.columns[3]: 'geographic_level',  # D: "Geographic Level"
        df.columns[4]: 'old_names',  # E: "Old names"
        df.columns[5]: 'city_class',  # F: "City Class"
        df.columns[6]: 'income_classification',  # G: "Income Classification"
        df.columns[7]: 'urban_rural',  # H: "Urban / Rural"
        df.columns[8]: 'population_2020',  # I: "2020 Population"
    }
    
    # Handle column K if it exists (Status)
    if len(df.columns) > 10:
        column_mapping[df.columns[10]] = 'status'
    
    df.rename(columns=column_mapping, inplace=True)
    
    # Process each row
    processed_data = []
    validation_warnings = []
    total_rows = len(df)
    
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            print(f"Processing row {idx}/{total_rows}...")
        # Skip rows with no PSGC code
        psgc_code = str(row.get('psgc_code', '')).strip()
        if not psgc_code or pd.isna(row.get('psgc_code')):
            continue
        
        # Parse PSGC code
        psgc_parts = parse_psgc_code(psgc_code)
        
        # Validate correspondence code
        raw_corr_code = row.get('correspondence_code')
        cleaned_corr_code, has_warning = validate_correspondence_code(raw_corr_code)
        
        if has_warning:
            validation_warnings.append({
                'psgc_code': psgc_code,
                'name': clean_value(row.get('name')),
                'correspondence_code': raw_corr_code,
                'issue': f'Non-integer correspondence code: {raw_corr_code}'
            })
        
        # Determine admin level first
        # Pass raw name to handle special cases correctly
        admin_level = determine_admin_level(
            row.get('geographic_level'), 
            psgc_parts,
            str(row.get('name', ''))
        )
        
        # Build the record
        record = {
            'psgc_code': psgc_code,
            'name': clean_value(row.get('name')),
            'correspondence_code': cleaned_corr_code,
            'geographic_level': clean_value(row.get('geographic_level')),
            'old_names': clean_value(row.get('old_names')),
            'city_class': clean_value(row.get('city_class')),
            'income_classification': clean_value(row.get('income_classification')),
            'urban_rural': clean_value(row.get('urban_rural')),
            'population_2020': int(float(row.get('population_2020'))) if pd.notna(row.get('population_2020')) and str(row.get('population_2020')).strip() not in ['-', ''] else None,
            'status': clean_value(row.get('status')) if 'status' in row else None,
            
            # Add parsed components
            'region_code': psgc_parts['region'],
            'province_code': psgc_parts['province'],
            'municipality_code': psgc_parts['municipality'],
            'barangay_code': psgc_parts['barangay'],
            
            # Add administrative level
            'admin_level': admin_level,
            
            # Add boolean flags for easier filtering
            # Use admin_level which already considers geographic_level
            'is_region': admin_level == 'region',
            'is_province': admin_level == 'province', 
            'is_city_municipality': admin_level == 'city_municipality',
            'is_barangay': admin_level == 'barangay',
            'is_submunicipality': admin_level == 'sub_municipality',
            'is_special_area': admin_level == 'special_area',
        }
        
        processed_data.append(record)
    
    return processed_data, validation_warnings


def save_as_json(data: List[Dict[str, Any]], output_path: str, indent: int = 2):
    """Save processed data as JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)
    print(f"Saved JSON to: {output_path}")


def save_as_csv(data: List[Dict[str, Any]], output_path: str):
    """Save processed data as CSV."""
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False, encoding='utf-8')
    print(f"Saved CSV to: {output_path}")


def save_as_jsonl(data: List[Dict[str, Any]], output_path: str):
    """Save processed data as JSONL (JSON Lines)."""
    with open(output_path, 'w', encoding='utf-8') as f:
        for record in data:
            json_line = json.dumps(record, ensure_ascii=False)
            f.write(json_line + '\n')
    print(f"Saved JSONL to: {output_path}")


def create_hierarchical_structure(data: List[Dict[str, Any]], skip_hierarchy: bool = False) -> Dict[str, Any]:
    """
    Create a hierarchical structure of the geographic data.
    """
    if skip_hierarchy:
        return {}
    
    hierarchy = {}
    
    # First, organize by region
    regions = [d for d in data if d['is_region']]
    
    for region in regions:
        region_code = region['psgc_code']
        hierarchy[region_code] = {
            'code': region_code,
            'name': region['name'],
            'type': 'region',
            'provinces': {}
        }
        
        # Find provinces in this region
        provinces = [d for d in data if d['is_province'] and d['region_code'] == region['region_code']]
        
        for province in provinces:
            province_code = province['psgc_code']
            hierarchy[region_code]['provinces'][province_code] = {
                'code': province_code,
                'name': province['name'],
                'type': 'province',
                'cities_municipalities': {}
            }
            
            # Find cities/municipalities in this province
            cities = [d for d in data if d['is_city_municipality'] 
                     and d['region_code'] == region['region_code']
                     and d['province_code'] == province['province_code']]
            
            for city in cities:
                city_code = city['psgc_code']
                hierarchy[region_code]['provinces'][province_code]['cities_municipalities'][city_code] = {
                    'code': city_code,
                    'name': city['name'],
                    'type': 'city_municipality',
                    'city_class': city['city_class'],
                    'income_classification': city['income_classification'],
                    'barangays': {}
                }
                
                # Find barangays in this city/municipality
                barangays = [d for d in data if d['is_barangay']
                           and d['region_code'] == region['region_code']
                           and d['province_code'] == province['province_code']
                           and d['municipality_code'] == city['municipality_code']]
                
                for barangay in barangays:
                    barangay_code = barangay['psgc_code']
                    hierarchy[region_code]['provinces'][province_code]['cities_municipalities'][city_code]['barangays'][barangay_code] = {
                        'code': barangay_code,
                        'name': barangay['name'],
                        'type': 'barangay',
                        'urban_rural': barangay['urban_rural'],
                        'population_2020': barangay['population_2020']
                    }
    
    return hierarchy


def main():
    """Main execution function."""
    # File paths
    input_file = 'PSGC-July-2025-Publication-Datafile.xlsx'
    
    # Check if input file exists
    if not Path(input_file).exists():
        print(f"Error: Input file '{input_file}' not found!")
        return
    
    # Process the data
    print("Processing PSGC data...")
    processed_data, validation_warnings = process_psgc_data(input_file)
    
    print(f"Processed {len(processed_data)} records")
    
    # Report validation warnings
    if validation_warnings:
        print(f"\n⚠️  WARNING: Found {len(validation_warnings)} records with invalid correspondence codes")
        print("These correspondence codes have non-zero decimal parts:")
        # Show first 10 warnings as examples
        for warning in validation_warnings[:10]:
            print(f"  - PSGC {warning['psgc_code']}: {warning['name']}")
            print(f"    Correspondence code: {warning['correspondence_code']}")
        if len(validation_warnings) > 10:
            print(f"  ... and {len(validation_warnings) - 10} more")
    else:
        print("✓ All correspondence codes are valid (integer values only)")
    
    # Save in different formats
    save_as_json(processed_data, 'psgc_data.json')
    save_as_csv(processed_data, 'psgc_data.csv')
    save_as_jsonl(processed_data, 'psgc_data.jsonl')
    
    # Create and save hierarchical structure (skip for now - very slow with large datasets)
    # Uncomment the following lines if you want hierarchical structure
    # print("Creating hierarchical structure...")
    # hierarchy = create_hierarchical_structure(processed_data)
    # save_as_json(hierarchy, 'psgc_hierarchy.json')
    
    # Print summary statistics
    print("\n=== Summary Statistics ===")
    df = pd.DataFrame(processed_data)
    print(f"Total records: {len(df)}")
    print(f"Regions: {df['is_region'].sum()}")
    print(f"Provinces: {df['is_province'].sum()}")
    
    # Separate cities and municipalities
    cities_municipalities = df[df['is_city_municipality'] == True]
    # Cities include those with "City" geographic_level OR those that are explicitly cities (like Isabela)
    cities = cities_municipalities[
        (cities_municipalities['geographic_level'] == 'City') | 
        (cities_municipalities['name'].str.contains('City of', na=False))
    ]
    municipalities = cities_municipalities[cities_municipalities['geographic_level'] == 'Mun']
    
    print(f"Cities: {len(cities)}")
    if len(cities) > 0:
        # Group by city class including those without geographic_level
        city_classes = cities['city_class'].value_counts()
        for city_class, count in city_classes.items():
            if pd.notna(city_class):
                print(f"  - {city_class}: {count}")
        # Check for cities without city_class
        no_class = cities[cities['city_class'].isna()]
        if len(no_class) > 0:
            print(f"  - No classification: {len(no_class)}")
    print(f"Municipalities: {len(municipalities)}")
    print(f"  Total Cities/Municipalities: {df['is_city_municipality'].sum()}")
    print(f"Sub-Municipalities: {df['is_submunicipality'].sum()}")
    print(f"Barangays: {df['is_barangay'].sum()}")
    
    # Sample output
    print("\n=== Sample Records ===")
    print("First 3 regions:")
    regions = df[df['is_region']].head(3)
    for _, r in regions.iterrows():
        print(f"  {r['psgc_code']}: {r['name']}")
    
    print("\nFirst 3 barangays:")
    barangays = df[df['is_barangay']].head(3)
    for _, b in barangays.iterrows():
        print(f"  {b['psgc_code']}: {b['name']} (Population: {b['population_2020']})")


if __name__ == '__main__':
    main()