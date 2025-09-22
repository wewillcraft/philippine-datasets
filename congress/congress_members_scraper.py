#!/usr/bin/env python3
"""
House of Representatives Members Scraper
Fetches member data from the Philippine House of Representatives API
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

API_URL = "https://api.v2.congress.hrep.online/hrep/api-v1/house-members/list"

class HouseMembersScraper:
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

    async def fetch_members(self, session: aiohttp.ClientSession,
                           page: int = 0, limit: int = 100,
                           filter_text: str = "", retries: int = 5,
                           retry_delay: int = 10) -> Dict:
        """Fetch members from the API with retry logic"""
        payload = {
            "page": page,
            "limit": limit,
            "filter": filter_text
        }

        print(f"Fetching members (page: {page + 1}, limit: {limit})...")

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
                            print(f"✅ Fetched {len(data['data']['rows'])} members from {data['data']['count']} total")
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
                    print(f"❌ Error fetching members after {retries} attempts: {e}")
                    return None

        return None

    def save_metadata(self, data: Dict, batch_num: int = None) -> Path:
        """Save raw API response to metadata directory"""
        if batch_num is not None:
            filename = f"house_members_batch_{batch_num:04d}.json"
        else:
            filename = f"house_members_all.json"
        filepath = self.metadata_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"📁 Saved metadata to {filepath}")
        return filepath

    def save_metadata_chunked(self, members: List[Dict], chunk_size: int = 50) -> List[Path]:
        """Save members in chunks to avoid massive files"""
        saved_files = []
        total_members = len(members)

        for i in range(0, total_members, chunk_size):
            batch_num = (i // chunk_size) + 1
            chunk = members[i:i + chunk_size]

            # Create metadata structure similar to API response
            chunk_data = {
                "success": True,
                "data": {
                    "rows": chunk,
                    "count": len(chunk),
                    "batch": batch_num,
                    "total_batches": (total_members + chunk_size - 1) // chunk_size
                }
            }

            filepath = self.save_metadata(chunk_data, batch_num)
            saved_files.append(filepath)

        return saved_files

    def convert_member_to_toml(self, member: Dict) -> Dict:
        """Convert API member format to TOML format"""
        # Build TOML structure
        toml_data = {
            'id': member.get('id', 0),
            'authorId': member.get('author_id', ''),
            'fullName': member.get('fullname', ''),
            'lastName': member.get('last_name', ''),
            'firstName': member.get('first_name', ''),
            'middleName': member.get('middle_name', '') or '',
            'suffix': member.get('suffix', '') or '',
            'nickName': member.get('nick_name', '') or '',
            'email': member.get('email', '') or '',
            'website': member.get('website', '') or '',
            'room': member.get('room', '') or '',
            'local': member.get('local', '') or '',
            'directLine': member.get('directline', '') or '',
            'chiefOfStaff': member.get('chief_of_staff', '') or '',
            'partyAffiliation': member.get('party_affilation', '') or '',
            'partyAffiliationDesc': member.get('party_affilation_desc', '') or '',
            'current': bool(member.get('current', False)),
            'lastScraped': datetime.now().isoformat()
        }

        # Add type and district if available
        if member.get('type'):
            toml_data['memberType'] = member.get('type')

        # Add district info if not party list
        if member.get('district'):
            toml_data['district'] = member.get('district', 0)

        # Add memberships if available
        if member.get('memberships'):
            memberships = member['memberships']
            toml_data['membershipInfo'] = {
                'congress': memberships.get('congress', 0),
                'congressDesc': memberships.get('congress_desc', ''),
                'type': memberships.get('type', 0),
                'typeDesc': memberships.get('type_desc', ''),
                'district': memberships.get('district', 0),
                'partyListId': memberships.get('party_list', 0),
                'partyListName': memberships.get('party_list_name', '')
            }

        # Add photo info
        if member.get('photo'):
            photo = member['photo']
            toml_data['photo'] = {
                'url': photo.get('url', ''),
                'size': photo.get('size', 0),
                'type': photo.get('type', '')
            }

        # Add committee memberships
        if member.get('committee_membership'):
            committees = []
            for comm in member['committee_membership']:
                if comm:
                    committees.append({
                        'code': comm.get('committee_code', ''),
                        'name': comm.get('name', ''),
                        'title': comm.get('title', '')
                    })
            if committees:
                toml_data['committees'] = committees

        # Add principal authored bills
        if member.get('principal_authored_bills'):
            bills = []
            # Group bills by congress
            bills_by_congress = {}
            for bill in member['principal_authored_bills']:
                if bill:
                    congress = bill.get('congress', 0)
                    if congress not in bills_by_congress:
                        bills_by_congress[congress] = []
                    bills_by_congress[congress].append({
                        'billNo': bill.get('bill_no', ''),
                        'date': bill.get('date', ''),
                        'name': bill.get('name', ''),
                        'nameCode': bill.get('name_code', ''),
                        'sequenceNo': bill.get('sequence_no', 0)
                    })

            # Convert to list format
            for congress, congress_bills in sorted(bills_by_congress.items()):
                bills.append({
                    'congress': congress,
                    'count': len(congress_bills),
                    'bills': congress_bills
                })

            if bills:
                toml_data['principalAuthoredBills'] = bills

        # Add coauthored bills if available
        if member.get('coauthored_bills'):
            coauthored = []
            # Group bills by congress
            bills_by_congress = {}
            for bill in member['coauthored_bills']:
                if bill:
                    congress = bill.get('congress', 0)
                    if congress not in bills_by_congress:
                        bills_by_congress[congress] = []
                    bills_by_congress[congress].append({
                        'billNo': bill.get('bill_no', ''),
                        'date': bill.get('date', ''),
                        'journalNo': bill.get('journal_no', ''),
                        'sessionNo': bill.get('session_no', '')
                    })

            # Convert to list format
            for congress, congress_bills in sorted(bills_by_congress.items()):
                coauthored.append({
                    'congress': congress,
                    'count': len(congress_bills),
                    'bills': congress_bills
                })

            if coauthored:
                toml_data['coauthoredBills'] = coauthored

        return toml_data

    def save_member_toml(self, member_data: Dict) -> Path:
        """Save individual member as TOML file"""
        author_id = member_data.get('authorId', '')
        if not author_id:
            # Use full name as fallback
            author_id = member_data.get('fullName', 'unknown').replace(' ', '_').replace('.', '')

        # Create directory structure - save all members in a common directory
        member_dir = self.base_dir / 'house' / 'members' / 'all'
        member_dir.mkdir(parents=True, exist_ok=True)

        # Save TOML file
        filename = f"{author_id}.toml"
        filepath = member_dir / filename

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                toml.dump(member_data, f)
        except Exception as e:
            raise Exception(f"Failed to save TOML file {filepath}: {e}")

        return filepath

    async def scrape_all_members(self, save_individual: bool = True,
                                skip_existing: bool = False, page_size: int = 100,
                                chunk_metadata: bool = False, metadata_chunk_size: int = 50,
                                max_members: int = None, incremental_save: bool = True,
                                filter_text: str = "") -> int:
        """Scrape all members from the API

        Args:
            save_individual: Whether to save individual TOML files
            skip_existing: Skip members that already exist as TOML files
            page_size: Number of members to fetch per page (API pagination)
            chunk_metadata: Whether to split metadata into chunks
            metadata_chunk_size: Number of members per metadata file when chunking
            max_members: Maximum total members to fetch (for testing), None for all
            incremental_save: Save metadata after each page fetch
            filter_text: Filter text for searching members
        """
        print(f"\n{'='*60}")
        print(f"Scraping All House Members")
        if filter_text:
            print(f"Filter: {filter_text}")
        print(f"{'='*60}")

        all_members = []
        page = 0
        total_count = None
        batch_counter = 1

        # Check existing metadata to potentially resume
        existing_batches = sorted(self.metadata_dir.glob(f"house_members_batch_*.json"))
        if existing_batches and incremental_save:
            # Load existing members from saved batches
            for batch_file in existing_batches:
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                    all_members.extend(batch_data['data']['rows'])
                    batch_counter = batch_data['data'].get('batch', 0) + 1
            print(f"📂 Found {len(existing_batches)} existing batches with {len(all_members)} members")
            page = len(all_members) // page_size

        async with aiohttp.ClientSession() as session:
            # Fetch all pages of members
            while True:
                data = await self.fetch_members(session, page=page, limit=page_size,
                                               filter_text=filter_text)

                if not data or not data.get('data'):
                    if page == 0:
                        print(f"❌ Failed to fetch data")
                        return 0
                    break

                members = data['data']['rows']
                if not members:
                    break

                # Get total count on first fetch
                if total_count is None:
                    total_count = data['data'].get('count', 0)

                # Add new members
                new_members_start = len(all_members)
                all_members.extend(members)

                print(f"  Fetched page {page + 1}: {len(all_members)}/{total_count} members")

                # Save incrementally if enabled
                if incremental_save and chunk_metadata:
                    # Save only the newly fetched members in chunks
                    new_members = all_members[new_members_start:]
                    for i in range(0, len(new_members), metadata_chunk_size):
                        chunk = new_members[i:i + metadata_chunk_size]
                        chunk_data = {
                            "success": True,
                            "data": {
                                "rows": chunk,
                                "count": len(chunk),
                                "batch": batch_counter,
                                "total_batches": -1,  # Unknown until completion
                                "page": page + 1,
                                "cumulative_count": new_members_start + i + len(chunk)
                            }
                        }
                        self.save_metadata(chunk_data, batch_counter)
                        batch_counter += 1
                    print(f"  💾 Saved batch(es) up to #{batch_counter - 1}")

                # Check if we've fetched all members or reached max limit
                if len(all_members) >= total_count:
                    break
                if max_members and len(all_members) >= max_members:
                    print(f"  Reached max_members limit of {max_members}")
                    all_members = all_members[:max_members]
                    break

                page += 1
                await asyncio.sleep(0.5)  # Be polite to the API

            members = all_members

            # If not incremental, save all at once
            if not incremental_save:
                if chunk_metadata:
                    saved_files = self.save_metadata_chunked(members, metadata_chunk_size)
                    print(f"📂 Saved metadata in {len(saved_files)} chunks")
                else:
                    # Create complete data structure for single file
                    complete_data = {
                        "success": True,
                        "data": {
                            "rows": members,
                            "count": len(members)
                        }
                    }
                    self.save_metadata(complete_data)
            else:
                print(f"📂 Incremental save completed with {batch_counter - 1} total batches")

            # Process individual members
            saved_count = 0
            skipped_count = 0
            error_count = 0

            if save_individual:
                print(f"\n📝 Processing {len(members)} members...")

                for i, member in enumerate(members, 1):
                    author_id = member.get('author_id', '')

                    if not author_id:
                        # Use full name as fallback
                        author_id = member.get('fullname', '').replace(' ', '_').replace('.', '')

                    if not author_id:
                        print(f"\n⚠️  Skipping member #{i} - no author_id or fullname")
                        continue

                    # Check if file already exists
                    if skip_existing:
                        member_path = self.base_dir / 'house' / 'members' / 'all' / f"{author_id}.toml"
                        if member_path.exists():
                            skipped_count += 1
                            if i % 10 == 0:
                                print(f"  Progress: {i}/{len(members)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")
                            continue

                    try:
                        # Convert to TOML format
                        toml_data = self.convert_member_to_toml(member)

                        # Save TOML file
                        filepath = self.save_member_toml(toml_data)
                        saved_count += 1
                    except Exception as e:
                        error_count += 1
                        print(f"\n❌ Error processing member {author_id}: {e}")
                        print(f"   Member data keys: {list(member.keys())}")
                        continue

                    if i % 10 == 0:
                        print(f"  Progress: {i}/{len(members)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")

                print(f"\n✅ Saved {saved_count} members, skipped {skipped_count} existing files, {error_count} errors")

            return len(members)

    def reprocess_existing_metadata(self, skip_existing: bool = False) -> int:
        """Reprocess existing metadata files to generate TOML files"""
        print(f"\n{'='*60}")
        print(f"Reprocessing existing metadata")
        print(f"{'='*60}")

        # Find all existing metadata batch files
        existing_batches = sorted(self.metadata_dir.glob(f"house_members_batch_*.json"))

        # Also check for single metadata file
        single_file = self.metadata_dir / f"house_members_all.json"
        if single_file.exists() and not existing_batches:
            existing_batches = [single_file]

        if not existing_batches:
            print(f"❌ No metadata files found")
            return 0

        print(f"📂 Found {len(existing_batches)} metadata file(s)")

        all_members = []

        # Load all members from metadata files
        for batch_file in existing_batches:
            try:
                with open(batch_file, 'r') as f:
                    batch_data = json.load(f)
                    rows = batch_data.get('data', {}).get('rows', [])
                    all_members.extend(rows)
                    print(f"  Loaded {len(rows)} members from {batch_file.name}")
            except Exception as e:
                print(f"  ❌ Error loading {batch_file.name}: {e}")
                continue

        if not all_members:
            print(f"❌ No members found in metadata files")
            return 0

        print(f"\n📝 Processing {len(all_members)} members...")

        saved_count = 0
        skipped_count = 0
        error_count = 0

        for i, member in enumerate(all_members, 1):
            author_id = member.get('author_id', '')

            if not author_id:
                # Use full name as fallback
                author_id = member.get('fullname', '').replace(' ', '_').replace('.', '')

            if not author_id:
                print(f"\n⚠️  Skipping member #{i} - no author_id or fullname")
                continue

            # Check if file already exists
            if skip_existing:
                member_path = self.base_dir / 'house' / 'members' / 'all' / f"{author_id}.toml"
                if member_path.exists():
                    skipped_count += 1
                    if i % 10 == 0:
                        print(f"  Progress: {i}/{len(all_members)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")
                    continue

            try:
                # Convert to TOML format
                toml_data = self.convert_member_to_toml(member)

                # Save TOML file
                filepath = self.save_member_toml(toml_data)
                saved_count += 1
            except Exception as e:
                error_count += 1
                print(f"\n❌ Error processing member {author_id}: {e}")
                continue

            if i % 10 == 0:
                print(f"  Progress: {i}/{len(all_members)} (saved {saved_count}, skipped {skipped_count}, errors {error_count})")

        print(f"\n✅ Reprocessing complete: saved {saved_count}, skipped {skipped_count}, errors {error_count}")
        return saved_count

    def create_index_file(self):
        """Create an index.yml file for all members"""
        member_dir = self.base_dir / 'house' / 'members' / 'all'

        if not member_dir.exists():
            print(f"❌ Directory {member_dir} does not exist")
            return

        # Get all TOML files
        toml_files = sorted(member_dir.glob("*.toml"))

        # Extract member IDs and organize by congress if possible
        members = []
        members_by_congress = {}

        for filepath in toml_files:
            member_id = filepath.stem  # Remove .toml extension
            members.append(member_id)

            # Try to read the file to get congress info
            try:
                with open(filepath, 'r') as f:
                    data = toml.load(f)
                    if 'principalAuthoredBills' in data and data['principalAuthoredBills']:
                        for bills_info in data['principalAuthoredBills']:
                            congress = bills_info.get('congress', 0)
                            if congress:
                                if congress not in members_by_congress:
                                    members_by_congress[congress] = []
                                if member_id not in members_by_congress[congress]:
                                    members_by_congress[congress].append(member_id)
            except:
                pass

        # Create index.yml
        index_data = {
            'total_members': len(members),
            'members': members,
            'members_by_congress': dict(sorted(members_by_congress.items())),
            'last_updated': datetime.now().isoformat()
        }

        index_path = member_dir / 'index.yml'
        with open(index_path, 'w') as f:
            import yaml
            yaml.dump(index_data, f, default_flow_style=False, sort_keys=False)

        print(f"📋 Created index file with {len(members)} members: {index_path}")


def main():
    parser = argparse.ArgumentParser(description='Scrape House of Representatives members')
    parser.add_argument('--skip-existing', action='store_true',
                       help='Skip members that already exist as TOML files')
    parser.add_argument('--metadata-only', action='store_true',
                       help='Only save metadata JSON, skip individual TOML files')
    parser.add_argument('--create-index', action='store_true',
                       help='Create index.yml file')
    parser.add_argument('--reprocess', action='store_true',
                       help='Reprocess existing metadata files to generate TOML files (no fetching)')
    parser.add_argument('--page-size', type=int, default=100,
                       help='Number of members per API page request (default: 100)')
    parser.add_argument('--max-members', type=int, default=None,
                       help='Maximum total members to fetch (for testing), fetches all if not specified')
    parser.add_argument('--chunk-metadata', action='store_true',
                       help='Split metadata JSON into smaller chunks')
    parser.add_argument('--metadata-chunk-size', type=int, default=50,
                       help='Number of members per metadata chunk file (default: 50)')
    parser.add_argument('--no-incremental', action='store_true',
                       help='Disable incremental saving (save all at once at the end)')
    parser.add_argument('--clean-metadata', action='store_true',
                       help='Remove existing metadata batch files before starting')
    parser.add_argument('--filter', default='',
                       help='Filter text for searching specific members')
    parser.add_argument('--dir', default='.',
                       help='Base directory for output (default: current directory)')
    parser.add_argument('--metadata-dir', default='metadata',
                       help='Directory for metadata files (default: metadata)')

    args = parser.parse_args()

    # Initialize scraper
    scraper = HouseMembersScraper(base_dir=args.dir, metadata_dir=args.metadata_dir)

    # Clean existing metadata if requested
    if args.clean_metadata:
        existing = list(scraper.metadata_dir.glob(f"house_members_batch_*.json"))
        existing.extend(scraper.metadata_dir.glob(f"house_members_all.json"))
        if existing:
            print(f"🧹 Removing {len(existing)} existing metadata files")
            for f in existing:
                f.unlink()

    # Run scraper
    print(f"🏛️  House of Representatives Members Scraper")
    print(f"📂 Output directory: {scraper.base_dir}")
    print(f"📁 Metadata directory: {scraper.metadata_dir}")

    if args.reprocess:
        # Reprocess existing metadata files
        print(f"\n📂 Reprocessing mode - using existing metadata files")
        count = scraper.reprocess_existing_metadata(skip_existing=args.skip_existing)

        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        print(f"Total reprocessed: {count} members")

        # Create index file if any members were reprocessed
        if count > 0:
            print(f"\n📋 Creating index file...")
            scraper.create_index_file()
    elif args.create_index:
        # Just create index file
        scraper.create_index_file()
    else:
        # Scrape members
        save_individual = not args.metadata_only

        count = asyncio.run(
            scraper.scrape_all_members(
                save_individual=save_individual,
                skip_existing=args.skip_existing,
                page_size=args.page_size,
                chunk_metadata=args.chunk_metadata,
                metadata_chunk_size=args.metadata_chunk_size,
                max_members=args.max_members,
                incremental_save=not args.no_incremental,
                filter_text=args.filter
            )
        )

        # Print summary
        print(f"\n{'='*60}")
        print(f"Summary")
        print(f"{'='*60}")
        print(f"Total: {count} members")

        # Create index file if requested
        if save_individual and count > 0:
            print(f"\n📋 Creating index file...")
            scraper.create_index_file()


if __name__ == '__main__':
    main()