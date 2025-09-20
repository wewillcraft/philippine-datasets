# Philippine Senate Bill Scraper

Python scraper for Philippine Senate bills from https://web.senate.gov.ph

## Main Scraper: `main.py`

A comprehensive scraper that:
- **Metadata Extraction**: Extracts senators, committees, and legislative statuses for Neo4j mapping
- **Discovery Phase**: Uses Selenium to navigate pages and discover all bill numbers
- **Fetching Phase**: Uses fast async HTTP requests to download bill details with "All Information" view

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Extract metadata for Neo4j mapping
```bash
# Extract metadata for all congresses (13-20)
python main.py --metadata

# Or specify specific congresses
python main.py --metadata --congress 19 20
```

### Discover all bill numbers
```bash
python main.py --discover --congress 19 --type ALL
```

### Fetch bill details
```bash
python main.py --fetch --congress 19 --type ALL --workers 30
```

### Complete workflow (all steps)
```bash
python main.py --metadata --discover --fetch --congress 19 --workers 30
```

### Additional options
```bash
# Force rediscovery (ignore cache)
python main.py --discover --congress 19 --type HBN --force

# Show browser during discovery
python main.py --discover --congress 19 --show-browser
```

## Options

- `--metadata`: Extract metadata (senators, committees, statuses)
- `--discover`: Run discovery phase to get bill numbers
- `--fetch`: Run fetching phase to download bill details
- `--congress`: Congress number(s) (e.g., 19, 20)
- `--type`: Bill type (SBN, HBN, or ALL)
- `--workers`: Number of concurrent workers for fetching (default: 20)
- `--dir`: Output directory for bills
- `--metadata-dir`: Directory for metadata and cache files (default: metadata)
- `--force`: Force rediscovery even if cache exists
- `--show-browser`: Show browser window during discovery

## Output Structure

### Metadata Directory (`metadata/`)

#### Congress Metadata Files
- `congress_13.json` - Metadata for Congress 13 (senators, committees, statuses)
- `congress_14.json` - Metadata for Congress 14
- `congress_15.json` - Metadata for Congress 15
- `congress_16.json` - Metadata for Congress 16
- `congress_17.json` - Metadata for Congress 17
- `congress_18.json` - Metadata for Congress 18
- `congress_19.json` - Metadata for Congress 19
- `congress_20.json` - Metadata for Congress 20
- `all_congresses.json` - Combined metadata for all congresses

#### Bill Discovery Cache Files
- `bills_congress_19_SBN.json` - Cached SBN bill numbers for Congress 19
- `bills_congress_19_HBN.json` - Cached HBN bill numbers for Congress 19
- `bills_congress_XX_[SBN|HBN].json` - Cached bill numbers for other congresses

### Bill Output (`congress/19/`)
```
congress/
└── 19/
    ├── SBN/
    │   ├── index.yml
    │   ├── SBN-00001.toml
    │   ├── SBN-00002.toml
    │   └── ...
    └── HBN/
        ├── index.yml
        ├── HBN-00001.toml
        ├── HBN-00004.toml
        ├── HBN-00005.toml
        ├── HBN-00014.toml
        └── ...
```

## Known Issues

- **HBN Bill Gaps**: HBN bills have non-consecutive numbering with massive gaps. For Congress 19, bills include: 1, 4, 5, 14, 24, 102, 198, 425, 1028... up to 11545
- **ASP.NET Forms**: The website uses ASP.NET postback forms for dropdown changes, which is why Selenium is used for discovery
- **Rate Limiting**: Be respectful and don't overwhelm the server. The scraper includes built-in delays

## Workflow for Neo4j Import

1. **Extract metadata** to get congress-specific reference data for senators, committees, and statuses (defaults to congresses 13-20)
2. **Discover bills** to get all bill numbers (handles non-consecutive HBN bills)
3. **Fetch details** with multiple workers for fast parallel processing
4. **Import to Neo4j** using the structured TOML files with proper codes for relationships