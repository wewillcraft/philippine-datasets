#!/usr/bin/env python3
"""
Neo4j Importer for Philippine Congress Data
Imports cleaned data into Neo4j graph database
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()


class Neo4jImporter:
    def __init__(self, uri: str = None, username: str = None, password: str = None,
                 cleaned_dir: str = "cleaned"):
        # Get Neo4j connection details
        self.uri = uri or os.getenv('NEO4J_URI')
        self.username = username or os.getenv('NEO4J_USERNAME')
        self.password = password or os.getenv('NEO4J_PASSWORD')

        if not all([self.uri, self.username, self.password]):
            raise ValueError("Missing Neo4j connection details in environment variables")

        self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
        self.cleaned_dir = Path(cleaned_dir)

        # Load data
        self.data = {}
        self.load_cleaned_data()

    def load_cleaned_data(self):
        """Load all cleaned data from JSON files"""
        files_to_load = [
            'congresses.json',
            'legislators.json',
            'bills.json',
            'committees.json',
            'bill_authors.json',
            'bill_committees.json',
            'bill_history.json',
            'bill_relationships.json'
        ]

        for filename in files_to_load:
            filepath = self.cleaned_dir / filename
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    key = filename.replace('.json', '')
                    self.data[key] = json.load(f)
                    print(f"📚 Loaded {len(self.data[key])} records from {filename}")
            else:
                print(f"⚠️  File not found: {filepath}")

    def create_indexes(self, session):
        """Create indexes for better query performance"""
        indexes = [
            "CREATE INDEX congress_number IF NOT EXISTS FOR (c:Congress) ON (c.number)",
            "CREATE INDEX legislator_id IF NOT EXISTS FOR (l:Legislator) ON (l.id)",
            "CREATE INDEX legislator_code IF NOT EXISTS FOR (l:Legislator) ON (l.code)",
            "CREATE INDEX bill_id IF NOT EXISTS FOR (b:Bill) ON (b.id)",
            "CREATE INDEX bill_number IF NOT EXISTS FOR (b:Bill) ON (b.number)",
            "CREATE INDEX committee_id IF NOT EXISTS FOR (c:Committee) ON (c.id)",
            "CREATE INDEX committee_code IF NOT EXISTS FOR (c:Committee) ON (c.code)",
            "CREATE INDEX status_code IF NOT EXISTS FOR (s:Status) ON (s.code)",
            "CREATE INDEX action_id IF NOT EXISTS FOR (a:LegislativeAction) ON (a.id)"
        ]

        for index in indexes:
            try:
                session.run(index)
                print(f"✅ Created index: {index.split('FOR')[1].split('ON')[0].strip()}")
            except Exception as e:
                print(f"⚠️  Index creation: {e}")

    def import_congresses(self, session):
        """Import Congress nodes"""
        if 'congresses' not in self.data:
            print("⚠️  No congress data to import")
            return

        query = """
        MERGE (c:Congress {number: $number})
        SET c.extracted_at = $extracted_at
        """

        count = 0
        for congress in self.data['congresses']:
            session.run(query,
                       number=congress['number'],
                       extracted_at=congress.get('extracted_at', ''))
            count += 1

        print(f"✅ Imported {count} Congress nodes")

    def import_legislators(self, session):
        """Import Legislator nodes"""
        if 'legislators' not in self.data:
            print("⚠️  No legislator data to import")
            return

        query = """
        MERGE (l:Legislator {id: $id})
        SET l.code = $code,
            l.name = $name,
            l.full_name = $full_name,
            l.type = $type,
            l.congresses = $congresses
        """

        count = 0
        for legislator in self.data['legislators']:
            session.run(query,
                       id=legislator['id'],
                       code=legislator['code'],
                       name=legislator['name'],
                       full_name=legislator['full_name'],
                       type=legislator['type'],
                       congresses=legislator.get('congresses', []))
            count += 1

        print(f"✅ Imported {count} Legislator nodes")

    def import_committees(self, session):
        """Import Committee nodes"""
        if 'committees' not in self.data:
            print("⚠️  No committee data to import")
            return

        query = """
        MERGE (c:Committee {id: $id})
        SET c.code = $code,
            c.name = $name,
            c.type = $type,
            c.congress = $congress
        """

        count = 0
        for committee in self.data['committees']:
            session.run(query,
                       id=committee['id'],
                       code=committee['code'],
                       name=committee['name'],
                       type=committee.get('type', 'regular'),
                       congress=committee['congress'])
            count += 1

        print(f"✅ Imported {count} Committee nodes")

    def import_bills(self, session):
        """Import Bill nodes"""
        if 'bills' not in self.data:
            print("⚠️  No bill data to import")
            return

        query = """
        MERGE (b:Bill {id: $id})
        SET b.number = $number,
            b.type = $type,
            b.congress = $congress,
            b.title = $title,
            b.longTitle = $longTitle,
            b.scope = $scope,
            b.filedDate = $filedDate,
            b.url = $url,
            b.pdfUrl = $pdfUrl,
            b.status = $status,
            b.statusDate = $statusDate,
            b.statusOrder = $statusOrder,
            b.urgent = $urgent,
            b.adminBill = $adminBill,
            b.source = $source,
            b.lastScraped = $lastScraped,
            b.subject = $subject
        """

        count = 0
        batch = []
        batch_size = 1000

        for bill in self.data['bills']:
            batch.append({
                'id': bill['id'],
                'number': bill['number'],
                'type': bill['type'],
                'congress': bill['congress'],
                'title': bill.get('title', ''),
                'longTitle': bill.get('longTitle', ''),
                'scope': bill.get('scope', 'National'),
                'filedDate': bill.get('filedDate', ''),
                'url': bill.get('url', ''),
                'pdfUrl': bill.get('pdfUrl', ''),
                'status': bill.get('status', ''),
                'statusDate': bill.get('statusDate', ''),
                'statusOrder': bill.get('statusOrder', 0),
                'urgent': bill.get('urgent', False),
                'adminBill': bill.get('adminBill', False),
                'source': bill.get('source', ''),
                'lastScraped': bill.get('lastScraped', ''),
                'subject': bill.get('subject', [])
            })

            if len(batch) >= batch_size:
                session.run(f"UNWIND $batch AS row {query}",
                           batch=batch)
                count += len(batch)
                batch = []
                print(f"  Processed {count} bills...")

        # Process remaining batch
        if batch:
            session.run(f"UNWIND $batch AS row {query.replace('$', 'row.')}",
                       batch=batch)
            count += len(batch)

        print(f"✅ Imported {count} Bill nodes")

    def import_legislator_congress_relationships(self, session):
        """Create SERVED_IN relationships between Legislators and Congresses"""
        query = """
        MATCH (l:Legislator)
        UNWIND l.congresses AS congress_num
        MATCH (c:Congress {number: congress_num})
        MERGE (l)-[r:SERVED_IN]->(c)
        """

        result = session.run(query)
        print(f"✅ Created SERVED_IN relationships")

    def import_congress_committee_relationships(self, session):
        """Create HAS_COMMITTEE relationships between Congresses and Committees"""
        query = """
        MATCH (com:Committee)
        MATCH (c:Congress {number: com.congress})
        MERGE (c)-[r:HAS_COMMITTEE]->(com)
        """

        result = session.run(query)
        print(f"✅ Created HAS_COMMITTEE relationships")

    def import_congress_bill_relationships(self, session):
        """Create HAS_BILL relationships between Congresses and Bills"""
        query = """
        MATCH (b:Bill)
        MATCH (c:Congress {number: b.congress})
        MERGE (c)-[r:HAS_BILL]->(b)
        """

        result = session.run(query)
        print(f"✅ Created HAS_BILL relationships")

    def import_bill_author_relationships(self, session):
        """Create AUTHORED and CO_AUTHORED relationships"""
        if 'bill_authors' not in self.data:
            print("⚠️  No bill author data to import")
            return

        # Primary authors
        primary_query = """
        UNWIND $batch AS row
        MATCH (b:Bill {id: row.bill_id})
        MATCH (l:Legislator {id: row.legislator_id})
        MERGE (l)-[r:AUTHORED]->(b)
        SET r.sequence = row.sequence
        """

        # Co-authors
        coauthor_query = """
        UNWIND $batch AS row
        MATCH (b:Bill {id: row.bill_id})
        MATCH (l:Legislator {id: row.legislator_id})
        MERGE (l)-[r:CO_AUTHORED]->(b)
        SET r.date = row.date
        """

        primary_batch = []
        coauthor_batch = []

        for rel in self.data['bill_authors']:
            if rel['type'] in ['primary', 'author']:
                primary_batch.append({
                    'bill_id': rel['bill_id'],
                    'legislator_id': rel['legislator_id'],
                    'sequence': rel.get('sequence', 1)
                })
            elif rel['type'] == 'coauthor':
                coauthor_batch.append({
                    'bill_id': rel['bill_id'],
                    'legislator_id': rel['legislator_id'],
                    'date': rel.get('date', '')
                })

        # Import primary authors
        if primary_batch:
            for i in range(0, len(primary_batch), 500):
                batch = primary_batch[i:i+500]
                session.run(primary_query, batch=batch)
            print(f"✅ Created {len(primary_batch)} AUTHORED relationships")

        # Import co-authors
        if coauthor_batch:
            for i in range(0, len(coauthor_batch), 500):
                batch = coauthor_batch[i:i+500]
                session.run(coauthor_query, batch=batch)
            print(f"✅ Created {len(coauthor_batch)} CO_AUTHORED relationships")

    def import_bill_committee_relationships(self, session):
        """Create REFERRED_TO relationships between Bills and Committees"""
        if 'bill_committees' not in self.data:
            print("⚠️  No bill committee data to import")
            return

        query = """
        UNWIND $batch AS row
        MATCH (b:Bill {id: row.bill_id})
        MATCH (c:Committee)
        WHERE c.name = row.committee_name AND c.congress = row.congress
        MERGE (b)-[r:REFERRED_TO]->(c)
        SET r.type = row.type,
            r.referralCode = row.referralCode,
            r.dateRead = row.dateRead
        """

        batch = []
        for rel in self.data['bill_committees']:
            batch.append({
                'bill_id': rel['bill_id'],
                'committee_name': rel['committee_name'],
                'type': rel.get('type', 'primary'),
                'referralCode': rel.get('referralCode', ''),
                'dateRead': rel.get('dateRead', ''),
                'congress': rel['congress']
            })

        if batch:
            for i in range(0, len(batch), 500):
                sub_batch = batch[i:i+500]
                session.run(query, batch=sub_batch)
            print(f"✅ Created {len(batch)} REFERRED_TO relationships")

    def import_bill_relationships(self, session):
        """Create bill-to-bill relationships (consolidated, substituted, etc.)"""
        if 'bill_relationships' not in self.data:
            print("⚠️  No bill relationship data to import")
            return

        query = """
        UNWIND $batch AS row
        MATCH (b1:Bill {id: row.from_bill})
        MATCH (b2:Bill {id: row.to_bill})
        CALL apoc.create.relationship(b1, row.type, {}, b2) YIELD rel
        RETURN count(rel)
        """

        # Check if APOC is available
        try:
            session.run("RETURN apoc.version()")
            has_apoc = True
        except:
            has_apoc = False
            print("⚠️  APOC not available, using alternative method for relationships")

        if has_apoc:
            batch = []
            for rel in self.data['bill_relationships']:
                batch.append({
                    'from_bill': rel['from_bill'],
                    'to_bill': rel['to_bill'],
                    'type': rel['type']
                })

            if batch:
                session.run(query, batch=batch)
                print(f"✅ Created {len(batch)} bill relationships")
        else:
            # Alternative without APOC - create specific relationship types
            rel_types = set(rel['type'] for rel in self.data['bill_relationships'])

            for rel_type in rel_types:
                if rel_type == 'MOTHER_OF':
                    query = """
                    MATCH (b1:Bill {id: $from_bill})
                    MATCH (b2:Bill {id: $to_bill})
                    MERGE (b1)-[r:MOTHER_OF]->(b2)
                    """
                elif rel_type == 'CONSOLIDATED_WITH':
                    query = """
                    MATCH (b1:Bill {id: $from_bill})
                    MATCH (b2:Bill {id: $to_bill})
                    MERGE (b1)-[r:CONSOLIDATED_WITH]->(b2)
                    """
                elif rel_type == 'SUBSTITUTED_BY':
                    query = """
                    MATCH (b1:Bill {id: $from_bill})
                    MATCH (b2:Bill {id: $to_bill})
                    MERGE (b1)-[r:SUBSTITUTED_BY]->(b2)
                    """
                else:
                    continue

                count = 0
                for rel in self.data['bill_relationships']:
                    if rel['type'] == rel_type:
                        session.run(query,
                                   from_bill=rel['from_bill'],
                                   to_bill=rel['to_bill'])
                        count += 1

                print(f"✅ Created {count} {rel_type} relationships")

    def import_legislative_history(self, session):
        """Import legislative history as LegislativeAction nodes"""
        if 'bill_history' not in self.data:
            print("⚠️  No legislative history data to import")
            return

        query = """
        UNWIND $batch AS row
        CREATE (a:LegislativeAction {
            id: row.id,
            date: row.date,
            action: row.action
        })
        WITH a, row
        MATCH (b:Bill {id: row.bill_id})
        CREATE (b)-[r:HAS_ACTION]->(a)
        """

        batch = []
        count = 0

        for hist in self.data['bill_history']:
            batch.append({
                'id': f"{hist['bill_id']}_{count}",
                'bill_id': hist['bill_id'],
                'date': hist.get('date', ''),
                'action': hist.get('action', '')
            })
            count += 1

            if len(batch) >= 500:
                session.run(query, batch=batch)
                batch = []

        if batch:
            session.run(query, batch=batch)

        print(f"✅ Imported {count} legislative history actions")

    def clear_database(self, session):
        """Clear all nodes and relationships from the database"""
        print("🗑️  Clearing existing data...")

        # Delete all relationships first
        session.run("MATCH ()-[r]->() DELETE r")
        print("  Deleted all relationships")

        # Delete all nodes
        session.run("MATCH (n) DELETE n")
        print("  Deleted all nodes")

    def import_all(self, clear_first: bool = False):
        """Import all data into Neo4j"""
        with self.driver.session() as session:
            if clear_first:
                self.clear_database(session)

            print("\n🔧 Creating indexes...")
            self.create_indexes(session)

            print("\n📊 Importing nodes...")

            # Import nodes
            self.import_congresses(session)
            self.import_legislators(session)
            self.import_committees(session)
            self.import_bills(session)

            print("\n🔗 Creating relationships...")

            # Import relationships
            self.import_legislator_congress_relationships(session)
            self.import_congress_committee_relationships(session)
            self.import_congress_bill_relationships(session)
            self.import_bill_author_relationships(session)
            self.import_bill_committee_relationships(session)
            self.import_bill_relationships(session)
            self.import_legislative_history(session)

            print("\n✅ Import completed!")

            # Get statistics
            result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY label
            """)

            print("\n📊 Database Statistics:")
            print("="*40)
            for record in result:
                print(f"  {record['label']}: {record['count']}")

            result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as type, count(r) as count
                ORDER BY type
            """)

            print("\n🔗 Relationship Statistics:")
            print("="*40)
            for record in result:
                print(f"  {record['type']}: {record['count']}")

    def close(self):
        """Close the Neo4j driver connection"""
        self.driver.close()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Import Philippine Congress data into Neo4j')
    parser.add_argument('--cleaned-dir', default='cleaned',
                       help='Directory containing cleaned JSON files (default: cleaned)')
    parser.add_argument('--clear', action='store_true',
                       help='Clear the database before importing')
    parser.add_argument('--uri', help='Neo4j URI (overrides environment variable)')
    parser.add_argument('--username', help='Neo4j username (overrides environment variable)')
    parser.add_argument('--password', help='Neo4j password (overrides environment variable)')

    args = parser.parse_args()

    print("🚀 Starting Neo4j import...")

    try:
        importer = Neo4jImporter(
            uri=args.uri,
            username=args.username,
            password=args.password,
            cleaned_dir=args.cleaned_dir
        )

        importer.import_all(clear_first=args.clear)

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    finally:
        if 'importer' in locals():
            importer.close()

    return 0


if __name__ == '__main__':
    exit(main())