# Philippine Congress Data Pipeline

A comprehensive data collection and processing pipeline for Philippine legislative data from both the Senate and House of Representatives, with Neo4j graph database integration for advanced relationship analysis.

## Overview

This pipeline consists of three main components:
1. **Data Collection**: Scrapers for Senate and House bills
2. **Data Cleaning**: Standardization and normalization of legislative data
3. **Database Import**: Neo4j graph database for relationship analysis

## Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp ../.env.example ../.env
# Edit ../.env and add:
# - NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD (for Neo4j)
# - CONGRESS_PH_BACKEND_HREP_SECRET (for House API)
```

## Complete Pipeline Workflow

### Step 1: Collect Senate Data

```bash
# Extract metadata for all congresses (13-20)
python senate_scraper.py --metadata

# Discover and fetch all bills for specific congresses
python senate_scraper.py --congress 19 20 --discover --fetch --workers 30

# Or fetch only missing files (resume from failures)
python senate_scraper.py --congress 19 20 --fetch --skip-existing
```

### Step 2: Collect House Data

```bash
# Fetch House bills for specific congresses
python congress_scraper.py --congress 19 20

# Fetch all available congresses (8-20)
python congress_scraper.py --all

# Skip existing files
python congress_scraper.py --congress 19 20 --skip-existing
```

### Step 3: Clean and Standardize Data

```bash
# Process all collected data into standardized format
python data_cleaner.py

# This creates cleaned JSON files in congress/cleaned/:
# - congresses.json      # Congress metadata
# - legislators.json     # Senators and Representatives
# - bills.json          # All bills in unified format
# - committees.json     # All committees
# - bill_authors.json   # Authorship relationships
# - bill_committees.json # Committee referrals
# - bill_history.json   # Legislative actions
# - summary.json        # Statistics and metadata
```

### Step 4: Import to Neo4j

```bash
# Import all cleaned data to Neo4j (clear existing data first)
python neo4j_importer.py --clear

# Import without clearing existing data
python neo4j_importer.py
```

## Data Structure

### Directory Layout
```
congress/
├── senate/                 # Senate bills (from senate_scraper.py)
│   ├── 20/
│   │   ├── SBN/           # Senate Bills
│   │   │   ├── SBN-00001.toml
│   │   │   └── ...
│   │   └── HBN/           # House Bills (received by Senate)
│   └── ...
├── house/                  # House bills (from congress_scraper.py)
│   ├── 20/
│   │   └── HB/            # House Bills
│   │       ├── HB00001.toml
│   │       └── ...
│   └── ...
├── cleaned/               # Standardized data (from data_cleaner.py)
│   ├── congresses.json
│   ├── legislators.json
│   ├── bills.json
│   └── ...
└── metadata/              # Raw API responses and metadata
    ├── congress_20.json
    ├── house_congress_20_bills.json
    └── ...
```

## Neo4j Graph Model

### Nodes
- **Congress**: Legislative congress (number, dates, sessions)
- **Legislator**: Senators and Representatives (code, name, type)
- **Bill**: Legislative bills (number, title, status, dates)
- **Committee**: Congressional committees (name, type, congress)
- **LegislativeAction**: Bill history events (date, action)

### Relationships
- `(Legislator)-[SERVED_IN]->(Congress)`
- `(Congress)-[HAS_COMMITTEE]->(Committee)`
- `(Congress)-[HAS_BILL]->(Bill)`
- `(Legislator)-[AUTHORED]->(Bill)` - Primary authors
- `(Legislator)-[CO_AUTHORED]->(Bill)` - Co-authors
- `(Bill)-[REFERRED_TO]->(Committee)`
- `(Bill)-[HAS_ACTION]->(LegislativeAction)`
- `(Bill)-[CONSOLIDATED_WITH]->(Bill)`
- `(Bill)-[SUBSTITUTED_BY]->(Bill)`
- `(Bill)-[MOTHER_OF]->(Bill)`

## Scripts Documentation

### `senate_scraper.py` - Senate Bill Scraper

Scrapes bills from the Philippine Senate website using Selenium for discovery and async HTTP for fetching.

**Key Features:**
- Metadata extraction (senators, committees, statuses)
- Bill discovery using Selenium
- Fast parallel fetching with async HTTP
- Resume capability with `--skip-existing`

**Usage:**
```bash
python senate_scraper.py --congress 19 20 --metadata --discover --fetch
```

### `congress_scraper.py` - House Bill Scraper

Fetches bills from the House of Representatives API.

**Key Features:**
- Direct API access (no web scraping)
- Congress number mapping (103→20th, 19→19th, etc.)
- Batch processing support
- TOML output format matching Senate structure

**Usage:**
```bash
python congress_scraper.py --congress 19 20 --skip-existing
```

**Congress Mapping:**
- Congress 20: API ID 103
- Congress 19: API ID 19
- Congress 18-8: API ID matches congress number

### `data_cleaner.py` - Data Standardization

Processes raw TOML files into standardized JSON for Neo4j import.

**Key Features:**
- Unified legislator IDs (SEN_*, REP_*)
- Name normalization and mapping
- Relationship extraction from bill data
- Committee standardization
- Bill status and history processing

**Usage:**
```bash
python data_cleaner.py
```

### `neo4j_importer.py` - Database Import

Imports cleaned data into Neo4j graph database.

**Key Features:**
- Batch import for performance
- Index creation for optimal queries
- Relationship mapping
- Clear database option
- Import statistics

**Usage:**
```bash
python neo4j_importer.py --clear  # Clear and import
python neo4j_importer.py          # Import only
```

## Example Queries (Neo4j)

After importing data, you can run powerful graph queries:

```cypher
// Find top 10 most prolific bill authors
MATCH (l:Legislator)-[r:AUTHORED]->(b:Bill)
RETURN l.name, count(b) as bills_authored
ORDER BY bills_authored DESC
LIMIT 10

// Find senators who frequently co-author bills together
MATCH (l1:Legislator)-[:CO_AUTHORED]->(b:Bill)<-[:CO_AUTHORED]-(l2:Legislator)
WHERE l1.type = 'senator' AND l2.type = 'senator' AND id(l1) < id(l2)
RETURN l1.name, l2.name, count(b) as collaborations
ORDER BY collaborations DESC
LIMIT 20

// Track a bill's journey through committees
MATCH (b:Bill {number: 'SBN-00001', congress: 19})-[r:REFERRED_TO]->(c:Committee)
RETURN b.title, c.name, r.type, r.dateRead
ORDER BY r.dateRead

// Find bills that were consolidated or substituted
MATCH (b1:Bill)-[r:CONSOLIDATED_WITH|SUBSTITUTED_BY]->(b2:Bill)
RETURN b1.number, type(r) as relationship, b2.number
LIMIT 20

// Analyze committee workload
MATCH (c:Committee)<-[:REFERRED_TO]-(b:Bill)
WHERE c.congress = 19
RETURN c.name, count(b) as bills_referred
ORDER BY bills_referred DESC
```

## Environment Variables

Create a `.env` file in the parent directory with:

```env
# Neo4j Database
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# House of Representatives API
CONGRESS_PH_BACKEND_HREP_SECRET=your-secret-key
```

## Common Issues and Solutions

### Senate Scraper Issues

**Timeout errors:**
- Use `--skip-existing` to resume
- Reduce `--workers` for stability
- Check internet connection

**Missing bills:**
- Some bills have server errors on the Senate website
- Non-consecutive numbering is normal for HBN bills

### House Scraper Issues

**API errors:**
- Verify environment variables are set
- Check API credentials are valid
- API may have rate limits

### Neo4j Import Issues

**Connection errors:**
- Verify Neo4j credentials
- Ensure database is running
- Check network connectivity

**Memory issues:**
- Import runs in batches automatically
- Reduce batch size if needed
- Consider clearing database first with `--clear`

## Performance Tips

1. **For large datasets:**
   - Use `--skip-existing` to avoid re-downloading
   - Process congresses individually
   - Run scrapers with appropriate worker counts

2. **For Neo4j imports:**
   - Clear database before full reimport
   - Indexes are created automatically
   - Monitor memory usage for large datasets

3. **For development:**
   - Test with single congress first
   - Use `--metadata-only` for quick tests
   - Check cleaned JSON files before import

## Contributing

When adding new features:
1. Update data models in `data_cleaner.py`
2. Add corresponding Neo4j import logic
3. Document new relationships and nodes
4. Test with sample data first

## License

Public domain - no rights reserved.