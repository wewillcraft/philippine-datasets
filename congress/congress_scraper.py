#!/usr/bin/env python3
"""
House of Representatives Bill Scraper
Fetches bill data from the Philippine House of Representatives API
"""

import os
import sys
import json
import toml
import argparse
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

load_dotenv()

CONGRESS_MAP = {
    103: 20,  # 20th Congress
    19: 19,   # 19th Congress
    18: 18,   # 18th Congress
    17: 17,   # 17th Congress
    16: 16,   # 16th Congress
    15: 15,   # 15th Congress
    14: 14,   # 14th Congress
    13: 13,   # 13th Congress
    12: 12,   # 12th Congress
    11: 11,   # 11th Congress
    10: 10,   # 10th Congress
    9: 9,     # 9th Congress
    8: 8,     # 8th Congress
}

API_URL = "https://api.v2.congress.hrep.online/hrep/api-v1/bills/list"

class HouseBillScraper:
    def __init__(self, base_dir: str = ".", metadata_dir: str = "metadata"):
        self.base_dir = Path(base_dir)
        self.metadata_dir = self.base_dir / metadata_dir
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

        # Load API credentials from environment
        self.api_secret = os.getenv('CONGRESS_PH_BACKEND_HREP_SECRET')

        if not self.api_secret:
            raise ValueError("Missing CONGRESS_PH_BACKEND_HREP_SECRET in environment variables")

        self.headers = {
            "x-hrep-website-backend": self.api_secret,
            "Content-Type": "application/json"
        }

    def get_api_congress_id(self, congress_num: int) -> int:
        """Convert congress number to API congress ID"""
        # Reverse lookup in CONGRESS_MAP
        for api_id, num in CONGRESS_MAP.items():
            if num == congress_num:
                return api_id
        # If not found, assume it's already the API ID
        return congress_num

    async def fetch_bills(self, session: aiohttp.ClientSession,
                         congress: int, page: int = 0, limit: int = 10000,
                         retries: int = 5, retry_delay: int = 10) -> Dict:
        """Fetch bills from the API for a specific congress with retry logic"""
        api_congress_id = self.get_api_congress_id(congress)

        payload = {
            "page": page,
            "limit": limit,
            "congress": api_congress_id,
            "filter": ""
        }

        print(f"Fetching bills for Congress {congress} (API ID: {api_congress_id}, limit: {limit})...")

        # Debug: Show request details
        if os.getenv('DEBUG'):
            print(f"📍 API URL: {API_URL}")
            print(f"📦 Payload: {json.dumps(payload, indent=2)}")
            print(f"🔑 Headers: x-hrep-website-backend: [HIDDEN], Content-Type: application/json")

        for attempt in range(retries):
            current_delay = retry_delay * (attempt + 1)  # Exponential backoff
            try:
                timeout = aiohttp.ClientTimeout(total=90)  # 90 second timeout
                async with session.post(API_URL, json=payload, headers=self.headers,
                                       timeout=timeout) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('success'):
                            print(f"✅ Fetched {len(data['data']['rows'])} bills from {data['data']['count']} total")
                            return data
                        else:
                            print(f"❌ API returned success=false: {data}")
                            return None
                    elif response.status == 504 or response.status == 502:
                        # Gateway timeout or bad gateway - retry
                        if attempt < retries - 1:
                            print(f"⏱️  Gateway timeout (attempt {attempt + 1}/{retries}), retrying in {current_delay} seconds...")
                            await asyncio.sleep(current_delay)
                            continue
                        else:
                            print(f"❌ HTTP {response.status} after {retries} attempts: Gateway timeout")
                            return None
                    else:
                        print(f"❌ HTTP {response.status}: {await response.text()}")
                        return None
            except asyncio.TimeoutError:
                if attempt < retries - 1:
                    print(f"⏱️  Request timeout (attempt {attempt + 1}/{retries}), retrying in {current_delay} seconds...")
                    await asyncio.sleep(current_delay)
                    continue
                else:
                    print(f"❌ Request timeout after {retries} attempts")
                    return None
            except Exception as e:
                if attempt < retries - 1:
                    print(f"⚠️  Error: {e} (attempt {attempt + 1}/{retries}), retrying in {current_delay} seconds...")
                    await asyncio.sleep(current_delay)
                    continue
                else:
                    print(f"❌ Error fetching bills after {retries} attempts: {e}")
                    return None

        return None

    def save_metadata(self, congress: int, data: Dict, batch_num: int = None) -> Path:
        """Save raw API response to metadata directory"""
        if batch_num is not None:
            filename = f"house_congress_{congress}_bills_batch_{batch_num:04d}.json"
        else:
            filename = f"house_congress_{congress}_bills.json"
        filepath = self.metadata_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"📁 Saved metadata to {filepath}")
        return filepath

    def save_metadata_chunked(self, congress: int, bills: List[Dict], chunk_size: int = 50) -> List[Path]:
        """Save bills in chunks to avoid massive files"""
        saved_files = []
        total_bills = len(bills)

        for i in range(0, total_bills, chunk_size):
            batch_num = (i // chunk_size) + 1
            chunk = bills[i:i + chunk_size]

            # Create metadata structure similar to API response
            chunk_data = {
                "success": True,
                "data": {
                    "rows": chunk,
                    "count": len(chunk),
                    "batch": batch_num,
                    "total_batches": (total_bills + chunk_size - 1) // chunk_size,
                    "congress": congress
                }
            }

            filepath = self.save_metadata(congress, chunk_data, batch_num)
            saved_files.append(filepath)

        return saved_files

    def convert_bill_to_toml(self, bill: Dict) -> Dict:
        """Convert API bill format to TOML format similar to Senate bills"""
        # Extract primary author and co-authors
        authors = bill.get('authors', [])
        primary_author = ""
        if authors and isinstance(authors, list) and len(authors) > 0:
            # Safely get the name from the first author
            primary_author = authors[0].get('name', authors[0].get('name_code', ''))

        co_authors = []
        if bill.get('coauthors'):
            co_authors = [ca.get('name', ca.get('name_code', '')) for ca in bill['coauthors'] if ca]

        # Build TOML structure
        toml_data = {
            'billNumber': bill.get('bill_no', ''),
            'billType': 'HB',
            'congress': CONGRESS_MAP.get(bill.get('congress', 0), bill.get('congress', 0)),
            'apiCongressId': bill.get('congress', 0),
            'url': f"https://www.congress.gov.ph/legisdocs/?v=billsresults&congress={bill.get('congress', '')}&q={bill.get('bill_no', '')}",
            'lastScraped': datetime.now().isoformat(),
            'title': (bill.get('title_short', '') or '').strip() or bill.get('bill_no', ''),
            'longTitle': bill.get('title_full', '') or '',
            'scope': bill.get('significance_desc') or 'National',
            'dateFiled': bill.get('date_filed') or '',
            'status': bill.get('status') or '',
            'statusOrder': float(bill.get('status_order') or 0),
            'urgent': bool(bill.get('urgent', False)),
            'adminBill': bool(bill.get('admin_bill', False)),
            'pdfUrl': bill.get('text_as_filed') or '',
            'fileSize': int(bill.get('size') or 0)
        }

        # Add primary author
        if primary_author:
            toml_data['author'] = primary_author

        # Add co-authors
        if co_authors:
            toml_data['coAuthors'] = co_authors

        # Add authors with details
        if authors:
            toml_data['authorsDetail'] = []
            for author in authors:
                if author:  # Skip None or empty authors
                    author_detail = {
                        'name': author.get('name', author.get('name_code', '')),
                        'nameCode': author.get('name_code', ''),
                        'date': author.get('date', ''),
                        'sequence': author.get('sequence_no', 0)
                    }
                    toml_data['authorsDetail'].append(author_detail)

        # Add co-authors with details
        if bill.get('coauthors'):
            toml_data['coAuthorsDetail'] = []
            for coauthor in bill['coauthors']:
                if coauthor:  # Skip None or empty coauthors
                    coauthor_detail = {
                        'name': coauthor.get('name', coauthor.get('name_code', '')),
                        'nameCode': coauthor.get('name_code', ''),
                        'date': coauthor.get('date', ''),
                        'journalNo': coauthor.get('journal_no', ''),
                        'sessionNo': coauthor.get('session_no', '')
                    }
                    toml_data['coAuthorsDetail'].append(coauthor_detail)

        # Add committee referrals
        committees = []

        # Primary referral
        if bill.get('first_reading'):
            fr = bill['first_reading']
            if fr.get('ref_name'):
                committees.append({
                    'name': fr['ref_name'],
                    'type': 'primary',
                    'referralCode': fr.get('referral', ''),
                    'dateRead': fr.get('date_read', '')
                })

        # Principal referrals
        if bill.get('principal_referral'):
            for ref in bill['principal_referral']:
                if ref.get('committee'):
                    committees.append({
                        'name': ref['committee'],
                        'type': 'principal',
                        'referralCode': ref.get('referral', '')
                    })

        # Secondary referrals
        if bill.get('secondary_referral'):
            for ref in bill['secondary_referral']:
                if ref.get('committee'):
                    committees.append({
                        'name': ref['committee'],
                        'type': 'secondary',
                        'referralCode': ref.get('referral', '')
                    })

        if committees:
            toml_data['committee'] = committees

        # Add reading information
        if bill.get('first_reading'):
            toml_data['firstReading'] = bill['first_reading']

        if bill.get('second_reading'):
            toml_data['secondReading'] = bill['second_reading']

        if bill.get('third_reading'):
            toml_data['thirdReading'] = bill['third_reading']

        # Add relationships with other bills
        if bill.get('mother_bills'):
            toml_data['motherBills'] = bill['mother_bills']

        if bill.get('consolidated_bills'):
            toml_data['consolidatedBills'] = bill['consolidated_bills']

        if bill.get('substituted_bills'):
            toml_data['substitutedBills'] = bill['substituted_bills']

        return toml_data

    def save_bill_toml(self, congress: int, bill_data: Dict) -> Path:
        """Save individual bill as TOML file"""
        bill_num = bill_data.get('billNumber', 'unknown')
        if not bill_num:
            raise ValueError("Bill has no bill number")

        bill_type = 'HB'  # House Bills

        # Create directory structure
        bill_dir = self.base_dir / 'house' / str(congress) / bill_type
        bill_dir.mkdir(parents=True, exist_ok=True)

        # Save TOML file
        filename = f"{bill_num}.toml"
        filepath = bill_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                toml.dump(bill_data, f)
        except Exception as e:
            raise Exception(f"Failed to save TOML file {filepath}: {e}")

        return filepath

    async def scrape_congress(self, congress: int, save_individual: bool = True,
                            skip_existing: bool = False, page_size: int = 10000,
                            chunk_metadata: bool = False, metadata_chunk_size: int = 50,
                            max_bills: int = None, incremental_save: bool = True) -> int:
        """Scrape all bills for a specific congress

        Args:
            congress: Congress number to scrape
            save_individual: Whether to save individual TOML files
            skip_existing: Skip bills that already exist as TOML files
            page_size: Number of bills to fetch per page (API pagination)
            chunk_metadata: Whether to split metadata into chunks
            metadata_chunk_size: Number of bills per metadata file when chunking
            max_bills: Maximum total bills to fetch (for testing), None for all
            incremental_save: Save metadata after each page fetch
        """
        print(f"\n{'='*60}")
        print(f"Scraping House Bills for Congress {congress}")
        print(f"{'='*60}")

        all_bills = []
        page = 0
        total_count = None
        batch_counter = 1

        # Check existing metadata to potentially resume
        existing_batches = sorted(self.metadata_dir.glob(f"house_congress_{congress}_bills_batch_*.json"))
        if existing_batches and incremental_save:
            # Load existing bills from saved batches
            for batch_file in existing_batches:
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                    all_bills.extend(batch_data['data']['rows'])
                    batch_counter = batch_data['data'].get('batch', 0) + 1
            print(f"📂 Found {len(existing_batches)} existing batches with {len(all_bills)} bills")
            page = len(all_bills) // page_size

        async with aiohttp.ClientSession() as session:
            # Fetch all pages of bills
            while True:
                data = await self.fetch_bills(session, congress, page=page, limit=page_size)

                if not data or not data.get('data'):
                    if page == 0:
                        print(f"❌ Failed to fetch data for congress {congress}")
                        return 0
                    break

                bills = data['data']['rows']
                if not bills:
                    break

                # Get total count on first fetch
                if total_count is None:
                    total_count = data['data'].get('count', 0)

                # Add new bills
                new_bills_start = len(all_bills)
                all_bills.extend(bills)

                print(f"  Fetched page {page + 1}: {len(all_bills)}/{total_count} bills")

                # Save incrementally if enabled
                if incremental_save and chunk_metadata:
                    # Save only the newly fetched bills in chunks
                    new_bills = all_bills[new_bills_start:]
                    for i in range(0, len(new_bills), metadata_chunk_size):
                        chunk = new_bills[i:i + metadata_chunk_size]
                        chunk_data = {
                            "success": True,
                            "data": {
                                "rows": chunk,
                                "count": len(chunk),
                                "batch": batch_counter,
                                "total_batches": -1,  # Unknown until completion
                                "congress": congress,
                                "page": page + 1,
                                "cumulative_count": new_bills_start + i + len(chunk)
                            }
                        }
                        self.save_metadata(congress, chunk_data, batch_counter)
                        batch_counter += 1
                    print(f"  💾 Saved batch(es) up to #{batch_counter - 1}")

                # Check if we've fetched all bills or reached max limit
                if len(all_bills) >= total_count:
                    break
                if max_bills and len(all_bills) >= max_bills:
                    print(f"  Reached max_bills limit of {max_bills}")
                    all_bills = all_bills[:max_bills]
                    break

                page += 1
                await asyncio.sleep(0.5)  # Be polite to the API

            bills = all_bills

            # If not incremental, save all at once
            if not incremental_save:
                if chunk_metadata:
                    saved_files = self.save_metadata_chunked(congress, bills, metadata_chunk_size)
                    print(f"📂 Saved metadata in {len(saved_files)} chunks")
                else:
                    # Create complete data structure for single file
                    complete_data = {
                        "success": True,
                        "data": {
                            "rows": bills,
                            "count": len(bills)
                        }
                    }
                    self.save_metadata(congress, complete_data)
            else:
                print(f"📂 Incremental save completed with {batch_counter - 1} total batches")

            # Process individual bills
            saved_count = 0
            skipped_count = 0

            if save_individual:
                print(f"\n📝 Processing {len(bills)} bills...")

                for i, bill in enumerate(bills, 1):
                    bill_num = bill.get('bill_no', '')

                    if not bill_num:
                        print(f"\n⚠️  Skipping bill #{i} - no bill_no field")
                        continue

                    # Check if file already exists
                    if skip_existing:
                        bill_path = self.base_dir / 'house' / str(congress) / 'HB' / f"{bill_num}.toml"
                        if bill_path.exists():
                            skipped_count += 1
                            if i % 100 == 0:
                                print(f"  Progress: {i}/{len(bills)} (skipped {skipped_count})")
                            continue

                    try:
                        # Convert to TOML format
                        toml_data = self.convert_bill_to_toml(bill)

                        # Save TOML file
                        filepath = self.save_bill_toml(congress, toml_data)
                        saved_count += 1
                    except Exception as e:
                        print(f"\n❌ Error processing bill {bill_num}: {e}")
                        print(f"   Bill data keys: {list(bill.keys())}")
                        if 'authors' in bill and bill['authors']:
                            print(f"   First author keys: {list(bill['authors'][0].keys()) if bill['authors'] else 'No authors'}")
                        continue

                    if i % 100 == 0:
                        print(f"  Progress: {i}/{len(bills)} (saved {saved_count}, skipped {skipped_count})")

                print(f"\n✅ Saved {saved_count} bills, skipped {skipped_count} existing files")

            return len(bills)

    async def scrape_multiple_congresses(self, congresses: List[int],
                                       save_individual: bool = True,
                                       skip_existing: bool = False,
                                       page_size: int = 10000,
                                       chunk_metadata: bool = False,
                                       metadata_chunk_size: int = 50,
                                       max_bills: int = None,
                                       incremental_save: bool = True) -> Dict[int, int]:
        """Scrape bills for multiple congresses"""
        results = {}

        for congress in congresses:
            count = await self.scrape_congress(
                congress, save_individual, skip_existing, page_size,
                chunk_metadata, metadata_chunk_size, max_bills, incremental_save
            )
            results[congress] = count
            await asyncio.sleep(1)  # Be polite to the API

        return results

    def reprocess_existing_metadata(self, congress: int, skip_existing: bool = False) -> int:
        """Reprocess existing metadata files to generate TOML files

        Args:
            congress: Congress number to reprocess
            skip_existing: Skip bills that already exist as TOML files

        Returns:
            Number of bills processed
        """
        print(f"\n{'='*60}")
        print(f"Reprocessing existing metadata for Congress {congress}")
        print(f"{'='*60}")

        # Find all existing metadata batch files
        existing_batches = sorted(self.metadata_dir.glob(f"house_congress_{congress}_bills_batch_*.json"))

        # Also check for single metadata file
        single_file = self.metadata_dir / f"house_congress_{congress}_bills.json"
        if single_file.exists() and not existing_batches:
            existing_batches = [single_file]

        if not existing_batches:
            print(f"❌ No metadata files found for congress {congress}")
            return 0

        print(f"📂 Found {len(existing_batches)} metadata file(s)")

        all_bills = []

        # Load all bills from metadata files
        for batch_file in existing_batches:
            try:
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                    rows = batch_data.get('data', {}).get('rows', [])
                    all_bills.extend(rows)
                    print(f"  Loaded {len(rows)} bills from {batch_file.name}")
            except Exception as e:
                print(f"  ❌ Error loading {batch_file.name}: {e}")
                continue

        if not all_bills:
            print(f"❌ No bills found in metadata files")
            return 0

        print(f"\n📝 Processing {len(all_bills)} bills...")

        saved_count = 0
        skipped_count = 0
        error_count = 0

        for i, bill in enumerate(all_bills, 1):
            bill_num = bill.get('bill_no', f"unknown_{i}")

            # Check if file already exists
            if skip_existing:
                bill_path = self.base_dir / 'house' / str(congress) / 'HB' / f"{bill_num}.toml"
                if bill_path.exists():
                    skipped_count += 1
                    if i % 100 == 0:
                        print(f"  Progress: {i}/{len(all_bills)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")
                    continue

            try:
                # Convert to TOML format
                toml_data = self.convert_bill_to_toml(bill)

                # Save TOML file
                filepath = self.save_bill_toml(congress, toml_data)
                saved_count += 1
            except Exception as e:
                error_count += 1
                print(f"\n❌ Error processing bill {bill_num}: {e}")
                if 'authors' in bill and bill['authors']:
                    print(f"   First author keys: {list(bill['authors'][0].keys()) if bill['authors'] else 'No authors'}")
                continue

            if i % 100 == 0:
                print(f"  Progress: {i}/{len(all_bills)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")

        print(f"\n✅ Reprocessing complete: saved {saved_count}, skipped {skipped_count}, errors {error_count}")
        return saved_count

    def create_index_file(self, congress: int):
        """Create an index.yml file for a congress (similar to Senate structure)"""
        bill_dir = self.base_dir / 'house' / str(congress) / 'HB'

        if not bill_dir.exists():
            print(f"❌ Directory {bill_dir} does not exist")
            return

        # Get all TOML files
        toml_files = sorted(bill_dir.glob("HB*.toml"))

        # Extract bill numbers
        bills = []
        for filepath in toml_files:
            bill_num = filepath.stem  # Remove .toml extension
            bills.append(bill_num)

        # Create index.yml
        index_data = {
            'congress': congress,
            'bill_type': 'HB',
            'total_bills': len(bills),
            'bills': bills,
            'last_updated': datetime.now().isoformat()
        }

        index_path = bill_dir / 'index.yml'
        with open(index_path, 'w') as f:
            import yaml
            yaml.dump(index_data, f, default_flow_style=False, sort_keys=False)

        print(f"📋 Created index file with {len(bills)} bills: {index_path}")


def main():
    parser = argparse.ArgumentParser(description='Scrape House of Representatives bills')
    parser.add_argument('--congress', nargs='+', type=int,
                       help='Congress number(s) to scrape (e.g., 20 19 18)')
    parser.add_argument('--all', action='store_true',
                       help='Scrape all available congresses (8-20)')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip bills that already exist as TOML files')
    parser.add_argument('--metadata-only', action='store_true',
                       help='Only save metadata JSON, skip individual TOML files')
    parser.add_argument('--create-index', action='store_true',
                       help='Create index.yml files for specified congresses')
    parser.add_argument('--reprocess', action='store_true',
                       help='Reprocess existing metadata files to generate TOML files (no fetching)')
    parser.add_argument('--page-size', type=int, default=1000,
                       help='Number of bills per API page request (default: 1000)')
    parser.add_argument('--max-bills', type=int, default=None,
                       help='Maximum total bills to fetch (for testing), fetches all if not specified')
    parser.add_argument('--chunk-metadata', action='store_true',
                       help='Split metadata JSON into smaller chunks')
    parser.add_argument('--metadata-chunk-size', type=int, default=50,
                       help='Number of bills per metadata chunk file (default: 50)')
    parser.add_argument('--no-incremental', action='store_true',
                       help='Disable incremental saving (save all at once at the end)')
    parser.add_argument('--clean-metadata', action='store_true',
                       help='Remove existing metadata batch files before starting')
    parser.add_argument('--dir', default='.',
                       help='Base directory for output (default: current directory)')
    parser.add_argument('--metadata-dir', default='metadata',
                       help='Directory for metadata files (default: metadata)')

    args = parser.parse_args()

    # Initialize scraper
    scraper = HouseBillScraper(base_dir=args.dir, metadata_dir=args.metadata_dir)

    # Determine which congresses to scrape
    if args.all:
        congresses = list(range(8, 21))  # Congress 8 to 20
    elif args.congress:
        congresses = args.congress
    else:
        # Default to congress 20
        congresses = [20]

    # Clean existing metadata if requested
    if args.clean_metadata:
        for congress in congresses:
            existing = list(scraper.metadata_dir.glob(f"house_congress_{congress}_bills_batch_*.json"))
            if existing:
                print(f"🧹 Removing {len(existing)} existing metadata files for congress {congress}")
                for f in existing:
                    f.unlink()

    # Run scraper
    print(f"🏛️  House of Representatives Bill Scraper")
    print(f"📂 Output directory: {scraper.base_dir}")
    print(f"📁 Metadata directory: {scraper.metadata_dir}")

    if args.reprocess:
        # Reprocess existing metadata files
        print(f"\n📂 Reprocessing mode - using existing metadata files")
        total_reprocessed = 0
        for congress in congresses:
            count = scraper.reprocess_existing_metadata(congress, skip_existing=args.skip_existing)
            total_reprocessed += count

        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        print(f"Total reprocessed: {total_reprocessed} bills")

        # Create index files if any bills were reprocessed
        if total_reprocessed > 0:
            print(f"\n📋 Creating index files...")
            for congress in congresses:
                scraper.create_index_file(congress)
    elif args.create_index:
        # Just create index files
        for congress in congresses:
            scraper.create_index_file(congress)
    else:
        # Scrape bills
        save_individual = not args.metadata_only

        results = asyncio.run(
            scraper.scrape_multiple_congresses(
                congresses,
                save_individual=save_individual,
                skip_existing=args.skip_existing,
                page_size=args.page_size,
                chunk_metadata=args.chunk_metadata,
                metadata_chunk_size=args.metadata_chunk_size,
                max_bills=args.max_bills,
                incremental_save=not args.no_incremental
            )
        )

        # Print summary
        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        total_bills = 0
        for congress, count in results.items():
            print(f"Congress {congress}: {count} bills")
            total_bills += count
        print(f"Total: {total_bills} bills")

        # Create index files if requested
        if save_individual:
            print(f"\n📋 Creating index files...")
            for congress in congresses:
                if results.get(congress, 0) > 0:
                    scraper.create_index_file(congress)


if __name__ == '__main__':
    main()