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


def parse_psgc_code(code: str) -> Dict[str, Optional[str]]:
    """
    Parse a 10-digit PSGC code into its components.
    Format: RRPPPMMBBB
    RR - Region code
    PPP - Province code/HUC
    MM - Municipality/City code
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


def determine_admin_level(geo_level: str, psgc_parts: Dict[str, str]) -> str:
    """Determine the administrative level based on geographic level and PSGC code."""
    geo_level_lower = str(geo_level).lower() if geo_level else ''
    
    if 'reg' in geo_level_lower:
        return 'region'
    elif 'prov' in geo_level_lower:
        return 'province'
    elif 'city' in geo_level_lower or 'mun' in geo_level_lower:
        return 'city_municipality'
    elif 'bgy' in geo_level_lower or 'brgy' in geo_level_lower or 'barangay' in geo_level_lower:
        return 'barangay'
    elif 'dist' in geo_level_lower:
        return 'district'
    elif 'sub' in geo_level_lower:
        return 'sub_municipality'
    
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


def process_psgc_data(file_path: str, sheet_name: str = 'PSGC') -> List[Dict[str, Any]]:
    """
    Process the PSGC Excel file and return cleaned data.
    """
    print(f"Reading Excel file: {file_path}")
    df = pd.read_excel(file_path, sheet_name=sheet_name)
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
        
        # Build the record
        record = {
            'psgc_code': psgc_code,
            'name': clean_value(row.get('name')),
            'correspondence_code': clean_value(row.get('correspondence_code')),
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
            'admin_level': determine_admin_level(
                row.get('geographic_level'), 
                psgc_parts
            ),
            
            # Add boolean flags for easier filtering
            'is_region': psgc_parts['province'] == '000',
            'is_province': psgc_parts['province'] != '000' and psgc_parts['municipality'] == '00',
            'is_city_municipality': psgc_parts['municipality'] != '00' and psgc_parts['barangay'] == '000',
            'is_barangay': psgc_parts['barangay'] != '000',
        }
        
        processed_data.append(record)
    
    return processed_data


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
    processed_data = process_psgc_data(input_file)
    
    print(f"Processed {len(processed_data)} records")
    
    # Save in different formats
    save_as_json(processed_data, 'psgc_data.json')
    save_as_csv(processed_data, 'psgc_data.csv')
    
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
    print(f"Cities/Municipalities: {df['is_city_municipality'].sum()}")
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