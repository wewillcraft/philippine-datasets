#!/usr/bin/env python3
"""
Data Cleaner for Philippine Congress Data
Processes Senate and House data into standardized format for Neo4j import
"""

import os
import json
import toml
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from collections import defaultdict


class CongressDataCleaner:
    def __init__(self, base_dir: str = "."):
        self.base_dir = Path(base_dir)
        self.cleaned_dir = self.base_dir / "cleaned"
        self.cleaned_dir.mkdir(parents=True, exist_ok=True)

        # Initialize data containers
        self.congresses = {}
        self.legislators = {}
        self.bills = []
        self.committees = {}
        self.bill_authors = []
        self.bill_committees = []
        self.bill_history = []
        self.bill_relationships = []

        # Name normalization mappings
        self.senator_name_map = {}
        self.rep_name_map = {}

    def load_metadata(self):
        """Load metadata files for congresses, senators, and committees"""
        metadata_dir = self.base_dir / "metadata"

        # Load all_congresses.json if it exists
        all_congress_file = metadata_dir / "all_congresses.json"
        if all_congress_file.exists():
            with open(all_congress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"📚 Loaded metadata from all_congresses.json")

        # Load individual congress metadata
        for congress_file in metadata_dir.glob("congress_*.json"):
            congress_num = int(congress_file.stem.split('_')[1])
            with open(congress_file, 'r', encoding='utf-8') as f:
                congress_data = json.load(f)

            self.congresses[congress_num] = {
                'number': congress_num,
                'extracted_at': congress_data.get('extracted_at', ''),
                'senators': {},
                'committees': {}
            }

            # Process senators
            if 'senators' in congress_data:
                for code, senator in congress_data['senators'].items():
                    senator_id = f"SEN_{code}"
                    self.legislators[senator_id] = {
                        'id': senator_id,
                        'code': code,
                        'name': senator['name'],
                        'full_name': senator.get('full_name', senator['name']),
                        'type': 'senator',
                        'congresses': [congress_num]
                    }
                    self.congresses[congress_num]['senators'][code] = senator_id
                    self.senator_name_map[senator['name']] = senator_id

            # Process committees
            if 'committees' in congress_data:
                for code, committee in congress_data['committees'].items():
                    committee_id = f"COM_{congress_num}_{code}"
                    self.committees[committee_id] = {
                        'id': committee_id,
                        'code': code,
                        'name': committee['name'],
                        'type': committee.get('type', 'regular'),
                        'congress': congress_num
                    }
                    self.congresses[congress_num]['committees'][code] = committee_id

            print(f"✅ Loaded metadata for Congress {congress_num}")

    def normalize_author_name(self, name: str, is_senator: bool = True) -> Optional[str]:
        """Normalize author name to legislator ID"""
        # Clean the name
        name = name.strip()

        if is_senator:
            # Direct lookup
            if name in self.senator_name_map:
                return self.senator_name_map[name]

            # Try variations
            # Remove extra spaces
            clean_name = re.sub(r'\s+', ' ', name)
            if clean_name in self.senator_name_map:
                return self.senator_name_map[clean_name]

            # Try last name, first name format
            if ',' in name:
                parts = name.split(',')
                if len(parts) == 2:
                    reversed_name = f"{parts[1].strip()}, {parts[0].strip()}"
                    if reversed_name in self.senator_name_map:
                        return self.senator_name_map[reversed_name]
        else:
            # For representatives (to be expanded)
            if name in self.rep_name_map:
                return self.rep_name_map[name]

        return None

    def process_senate_bills(self):
        """Process Senate bill TOML files"""
        senate_dir = self.base_dir / "senate"

        if not senate_dir.exists():
            print(f"⚠️  Senate directory not found: {senate_dir}")
            return

        bill_count = 0

        # Process each congress
        for congress_dir in sorted(senate_dir.iterdir()):
            if not congress_dir.is_dir() or not congress_dir.name.isdigit():
                continue

            congress_num = int(congress_dir.name)

            # Process bill types (SBN, HBN)
            for bill_type_dir in congress_dir.iterdir():
                if not bill_type_dir.is_dir():
                    continue

                bill_type = bill_type_dir.name

                # Process each bill TOML file
                for toml_file in bill_type_dir.glob("*.toml"):
                    if toml_file.name == "index.yml":
                        continue

                    try:
                        with open(toml_file, 'rb') as f:
                            bill_data = toml.load(f)

                        bill_id = f"{congress_num}_{bill_type}_{bill_data['billNumber']}"

                        # Create bill record
                        bill = {
                            'id': bill_id,
                            'number': bill_data['billNumber'],
                            'type': bill_type,
                            'congress': congress_num,
                            'title': bill_data.get('title', ''),
                            'longTitle': bill_data.get('longTitle', ''),
                            'scope': bill_data.get('scope', 'National'),
                            'filedDate': bill_data.get('filedDate', ''),
                            'url': bill_data.get('url', ''),
                            'pdfUrl': bill_data.get('pdfUrl', ''),
                            'subject': bill_data.get('subject', []),
                            'lastScraped': bill_data.get('lastScraped', ''),
                            'source': 'senate'
                        }

                        # Add status if available
                        if 'status' in bill_data:
                            bill['status'] = bill_data['status'].get('status', '')
                            bill['statusDate'] = bill_data['status'].get('date', '')

                        self.bills.append(bill)

                        # Process authors
                        if 'author' in bill_data:
                            # Handle comma-separated authors
                            authors = bill_data['author']
                            if isinstance(authors, str):
                                author_list = [a.strip() for a in authors.split(',')]
                                # Group pairs for "LastName, FirstName" format
                                processed_authors = []
                                i = 0
                                while i < len(author_list):
                                    if i + 1 < len(author_list) and not any(c.isdigit() for c in author_list[i]):
                                        # Likely a "LastName, FirstName" pair
                                        full_name = f"{author_list[i]}, {author_list[i+1]}"
                                        processed_authors.append(full_name)
                                        i += 2
                                    else:
                                        processed_authors.append(author_list[i])
                                        i += 1

                                for seq, author_name in enumerate(processed_authors, 1):
                                    legislator_id = self.normalize_author_name(author_name, is_senator=True)
                                    if legislator_id:
                                        self.bill_authors.append({
                                            'bill_id': bill_id,
                                            'legislator_id': legislator_id,
                                            'type': 'primary',
                                            'sequence': seq
                                        })

                        # Process committees
                        if 'committee' in bill_data:
                            committees = bill_data['committee']
                            if isinstance(committees, dict):
                                committees = [committees]
                            elif not isinstance(committees, list):
                                committees = []

                            for comm in committees:
                                if isinstance(comm, dict):
                                    self.bill_committees.append({
                                        'bill_id': bill_id,
                                        'committee_name': comm.get('name', ''),
                                        'type': comm.get('type', 'primary'),
                                        'congress': congress_num
                                    })

                        # Process legislative history
                        if 'legislativeHistory' in bill_data:
                            for hist in bill_data['legislativeHistory']:
                                self.bill_history.append({
                                    'bill_id': bill_id,
                                    'date': hist.get('date', ''),
                                    'action': hist.get('action', '')
                                })

                        bill_count += 1

                    except Exception as e:
                        print(f"❌ Error processing {toml_file}: {e}")

        print(f"✅ Processed {bill_count} Senate bills")

    def process_house_bills(self):
        """Process House bill TOML files"""
        house_dir = self.base_dir / "house"

        if not house_dir.exists():
            print(f"⚠️  House directory not found: {house_dir}")
            return

        bill_count = 0

        # Process each congress
        for congress_dir in sorted(house_dir.iterdir()):
            if not congress_dir.is_dir() or not congress_dir.name.isdigit():
                continue

            congress_num = int(congress_dir.name)

            # Process HB directory
            hb_dir = congress_dir / "HB"
            if not hb_dir.exists():
                continue

            # Process each bill TOML file
            for toml_file in hb_dir.glob("*.toml"):
                if toml_file.name == "index.yml":
                    continue

                try:
                    with open(toml_file, 'rb') as f:
                        bill_data = toml.load(f)

                    bill_id = f"{congress_num}_HB_{bill_data['billNumber']}"

                    # Create bill record
                    bill = {
                        'id': bill_id,
                        'number': bill_data['billNumber'],
                        'type': 'HB',
                        'congress': congress_num,
                        'title': bill_data.get('title', ''),
                        'longTitle': bill_data.get('longTitle', ''),
                        'scope': bill_data.get('scope', 'National'),
                        'filedDate': bill_data.get('dateFiled', ''),
                        'url': bill_data.get('url', ''),
                        'pdfUrl': bill_data.get('pdfUrl', ''),
                        'status': bill_data.get('status', ''),
                        'statusOrder': bill_data.get('statusOrder', 0),
                        'urgent': bill_data.get('urgent', False),
                        'adminBill': bill_data.get('adminBill', False),
                        'lastScraped': bill_data.get('lastScraped', ''),
                        'source': 'house'
                    }

                    self.bills.append(bill)

                    # Process primary author
                    if 'author' in bill_data:
                        author_name = bill_data['author']
                        # Create or get representative ID
                        rep_id = f"REP_{author_name.replace(' ', '_').replace(',', '').upper()}"
                        if rep_id not in self.legislators:
                            self.legislators[rep_id] = {
                                'id': rep_id,
                                'code': rep_id,
                                'name': author_name,
                                'full_name': author_name,
                                'type': 'representative',
                                'congresses': [congress_num]
                            }
                        else:
                            if congress_num not in self.legislators[rep_id]['congresses']:
                                self.legislators[rep_id]['congresses'].append(congress_num)

                        self.bill_authors.append({
                            'bill_id': bill_id,
                            'legislator_id': rep_id,
                            'type': 'primary',
                            'sequence': 1
                        })

                    # Process authors with details
                    if 'authorsDetail' in bill_data:
                        for author in bill_data['authorsDetail']:
                            author_name = author['name']
                            rep_id = f"REP_{author_name.replace(' ', '_').replace(',', '').upper()}"

                            if rep_id not in self.legislators:
                                self.legislators[rep_id] = {
                                    'id': rep_id,
                                    'code': author.get('nameCode', rep_id),
                                    'name': author_name,
                                    'full_name': author_name,
                                    'type': 'representative',
                                    'congresses': [congress_num]
                                }
                            else:
                                if congress_num not in self.legislators[rep_id]['congresses']:
                                    self.legislators[rep_id]['congresses'].append(congress_num)

                            self.bill_authors.append({
                                'bill_id': bill_id,
                                'legislator_id': rep_id,
                                'type': 'author',
                                'sequence': author.get('sequence', 0),
                                'date': author.get('date', '')
                            })

                    # Process co-authors
                    if 'coAuthorsDetail' in bill_data:
                        for coauthor in bill_data['coAuthorsDetail']:
                            author_name = coauthor['name']
                            rep_id = f"REP_{author_name.replace(' ', '_').replace(',', '').upper()}"

                            if rep_id not in self.legislators:
                                self.legislators[rep_id] = {
                                    'id': rep_id,
                                    'code': coauthor.get('nameCode', rep_id),
                                    'name': author_name,
                                    'full_name': author_name,
                                    'type': 'representative',
                                    'congresses': [congress_num]
                                }
                            else:
                                if congress_num not in self.legislators[rep_id]['congresses']:
                                    self.legislators[rep_id]['congresses'].append(congress_num)

                            self.bill_authors.append({
                                'bill_id': bill_id,
                                'legislator_id': rep_id,
                                'type': 'coauthor',
                                'date': coauthor.get('date', '')
                            })

                    # Process committees
                    if 'committee' in bill_data:
                        committees = bill_data['committee']
                        if isinstance(committees, dict):
                            committees = [committees]
                        elif not isinstance(committees, list):
                            committees = []

                        for comm in committees:
                            if isinstance(comm, dict):
                                self.bill_committees.append({
                                    'bill_id': bill_id,
                                    'committee_name': comm.get('name', ''),
                                    'type': comm.get('type', 'primary'),
                                    'referralCode': comm.get('referralCode', ''),
                                    'dateRead': comm.get('dateRead', ''),
                                    'congress': congress_num
                                })

                    # Process bill relationships
                    if 'motherBills' in bill_data and bill_data['motherBills']:
                        for mother in bill_data['motherBills']:
                            self.bill_relationships.append({
                                'from_bill': bill_id,
                                'to_bill': mother,
                                'type': 'MOTHER_OF'
                            })

                    if 'consolidatedBills' in bill_data and bill_data['consolidatedBills']:
                        for consolidated in bill_data['consolidatedBills']:
                            self.bill_relationships.append({
                                'from_bill': bill_id,
                                'to_bill': consolidated,
                                'type': 'CONSOLIDATED_WITH'
                            })

                    if 'substitutedBills' in bill_data and bill_data['substitutedBills']:
                        for substituted in bill_data['substitutedBills']:
                            self.bill_relationships.append({
                                'from_bill': bill_id,
                                'to_bill': substituted,
                                'type': 'SUBSTITUTED_BY'
                            })

                    bill_count += 1

                except Exception as e:
                    print(f"❌ Error processing {toml_file}: {e}")

        print(f"✅ Processed {bill_count} House bills")

    def save_cleaned_data(self):
        """Save all cleaned data to JSON files"""
        # Save congresses
        congress_file = self.cleaned_dir / "congresses.json"
        with open(congress_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.congresses.values()), f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.congresses)} congresses to {congress_file}")

        # Save legislators
        legislators_file = self.cleaned_dir / "legislators.json"
        with open(legislators_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.legislators.values()), f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.legislators)} legislators to {legislators_file}")

        # Save bills
        bills_file = self.cleaned_dir / "bills.json"
        with open(bills_file, 'w', encoding='utf-8') as f:
            json.dump(self.bills, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.bills)} bills to {bills_file}")

        # Save committees
        committees_file = self.cleaned_dir / "committees.json"
        with open(committees_file, 'w', encoding='utf-8') as f:
            json.dump(list(self.committees.values()), f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.committees)} committees to {committees_file}")

        # Save bill authors
        bill_authors_file = self.cleaned_dir / "bill_authors.json"
        with open(bill_authors_file, 'w', encoding='utf-8') as f:
            json.dump(self.bill_authors, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.bill_authors)} bill-author relationships to {bill_authors_file}")

        # Save bill committees
        bill_committees_file = self.cleaned_dir / "bill_committees.json"
        with open(bill_committees_file, 'w', encoding='utf-8') as f:
            json.dump(self.bill_committees, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.bill_committees)} bill-committee relationships to {bill_committees_file}")

        # Save bill history
        bill_history_file = self.cleaned_dir / "bill_history.json"
        with open(bill_history_file, 'w', encoding='utf-8') as f:
            json.dump(self.bill_history, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.bill_history)} legislative history entries to {bill_history_file}")

        # Save bill relationships
        bill_relationships_file = self.cleaned_dir / "bill_relationships.json"
        with open(bill_relationships_file, 'w', encoding='utf-8') as f:
            json.dump(self.bill_relationships, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved {len(self.bill_relationships)} bill relationships to {bill_relationships_file}")

        # Save summary
        summary = {
            'generated_at': datetime.now().isoformat(),
            'statistics': {
                'congresses': len(self.congresses),
                'legislators': len(self.legislators),
                'senators': len([l for l in self.legislators.values() if l['type'] == 'senator']),
                'representatives': len([l for l in self.legislators.values() if l['type'] == 'representative']),
                'bills': len(self.bills),
                'senate_bills': len([b for b in self.bills if b['source'] == 'senate']),
                'house_bills': len([b for b in self.bills if b['source'] == 'house']),
                'committees': len(self.committees),
                'bill_authors': len(self.bill_authors),
                'bill_committees': len(self.bill_committees),
                'bill_history': len(self.bill_history),
                'bill_relationships': len(self.bill_relationships)
            }
        }

        summary_file = self.cleaned_dir / "summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved summary to {summary_file}")

    def clean(self):
        """Main cleaning process"""
        print("🧹 Starting data cleaning process...")

        # Load metadata
        print("\n📚 Loading metadata...")
        self.load_metadata()

        # Process Senate bills
        print("\n🏛️  Processing Senate bills...")
        self.process_senate_bills()

        # Process House bills
        print("\n🏛️  Processing House bills...")
        self.process_house_bills()

        # Save cleaned data
        print("\n💾 Saving cleaned data...")
        self.save_cleaned_data()

        print("\n✅ Data cleaning completed!")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Clean and standardize Philippine Congress data')
    parser.add_argument('--dir', default='.',
                       help='Base directory containing congress data (default: current directory)')

    args = parser.parse_args()

    cleaner = CongressDataCleaner(base_dir=args.dir)
    cleaner.clean()


if __name__ == '__main__':
    main()