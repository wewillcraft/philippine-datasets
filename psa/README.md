# Philippine Statistics Authority

## Philippine Standard Geographic Code (PSGC)

The `PSGC-July-2025-Publication-Datafile.xlsx` file is taken from
https://psa.gov.ph/classification/psgc.

The 10-digit PSGC code comprises of RRPPPMMBBB:

- Region Code (RR)
- Province Code/HUC (PPP)
- Municipal/City Code (MM)
- Barangay Code (BBB)

The Municipal/City Identifier (PPPMM) is a combination of:

- Province Code/HUC (PPP)
- Municipal/City Code (MM)

The Barangay Identifier (PPPMMBBB) is a combination of:

- Province Code/HUC (PPP)
- Municipal/City Code (MM)
- Barangay Code (BBB)

Here are the Geographic Levels:

- Reg - Region
- Prov - Province
- Mun - Municipality
- Bgy - Barangay
- Dist - District
- SubMun - Sub-municipality or Municipal District

## Running the Parser Scripts

This repository includes scripts to parse and clean the PSGC Excel data for use
in applications and APIs.

### Python Script

**Prerequisites:**

```bash
pip3 install -r requirements.txt
```

**Run the script:**

```bash
python3 parse_psgc.py
```

It will generate:

- `psgc_data.json` - Complete dataset in JSON format with parsed PSGC codes and
  metadata
- `psgc_data.csv` - Complete dataset in CSV format for spreadsheet/database
  import

### Data Structure

Each record includes:

- Original columns from the Excel file (PSGC code, name, geographic level,
  population, etc.)
- Parsed PSGC components (region_code, province_code, municipality_code,
  barangay_code)
- Administrative level classification
- Boolean flags for easy filtering (is_region, is_province,
  is_city_municipality, is_barangay)
