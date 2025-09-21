# Philippine Senate Bill Scraper

Python scraper for Philippine Senate bills from https://web.senate.gov.ph

## Main Scraper: `main.py`

A comprehensive scraper that:
- **Metadata Extraction**: Extracts senators, committees, and legislative statuses for Neo4j mapping
- **Discovery Phase**: Uses Selenium to navigate pages and discover all bill numbers
- **Fetching Phase**: Uses fast async HTTP requests to download bill details with "All Information" view
- **Skip Existing**: Can resume from failures by skipping already downloaded files

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic workflow (discover and fetch)
```bash
# Default: Congress 19, all bill types
python main.py

# Specific congress
python main.py --congress 19

# Multiple congresses
python main.py --congress 16 17 18 19 20
```

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

### Resume from failures (NEW)
```bash
# Only download missing files for ALL cached congresses
python main.py --fetch --skip-existing

# For specific congresses
python main.py --congress 16 17 --fetch --skip-existing

# The scraper will automatically detect all congresses with cached metadata
# and process them all when no --congress is specified
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
- `--skip-existing`: Only download missing files, skip existing ones (NEW)
- `--congress`: Congress number(s) (e.g., 19, 20) - if omitted, processes all cached congresses when fetching
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

### Bill Output (`senate/19/`)
```
senate/
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

## Recovery from Errors

If the scraper encounters timeouts or connection errors:

```bash
# Use --skip-existing to only download missing files
python main.py --congress 16 17 --fetch --skip-existing
```

This will:
1. Check metadata JSON files for expected bills
2. Scan congress directories for existing TOML files
3. Only attempt to download missing files
4. Update index.yml with all existing bills

### Common Error Messages

**Timeout errors:**
```
⏱️  Timeout for SBN-1233
```
Solution: Use `--skip-existing` to retry only failed downloads

**Server disconnection:**
```
❌ Error fetching SBN-1791: Server disconnected
```
Solution: Use `--skip-existing` and optionally reduce `--workers` to decrease server load

## Known Issues

- **Senate Website Data Errors**: Some bills appear in search results but their detail pages return server errors (e.g., SBN-1273 in Congress 19). These are bugs on the Senate website itself.
- **HBN Bill Gaps**: HBN bills have non-consecutive numbering with massive gaps. For Congress 19, bills include: 1, 4, 5, 14, 24, 102, 198, 425, 1028... up to 11545
- **ASP.NET Forms**: The website uses ASP.NET postback forms for dropdown changes, which is why Selenium is used for discovery
- **Rate Limiting**: Be respectful and don't overwhelm the server. The scraper includes built-in delays

## Workflow for Neo4j Import

1. **Extract metadata** to get congress-specific reference data for senators, committees, and statuses (defaults to congresses 13-20)
2. **Discover bills** to get all bill numbers (handles non-consecutive HBN bills)
3. **Fetch details** with multiple workers for fast parallel processing
4. **Import to Neo4j** using the structured TOML files with proper codes for relationships

## Performance Tips

- Use `--workers` to adjust concurrent requests (default: 20)
- Higher worker counts speed up fetching but may cause more timeouts
- Use `--skip-existing` for incremental updates or recovery from failures
- Discovery phase requires browser automation and is slower than fetching