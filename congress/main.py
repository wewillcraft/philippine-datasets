#!/usr/bin/env python3
"""
Main Philippine Senate Bill Scraper
Combines Selenium for discovery and async HTTP for fetching
"""

import asyncio
import aiohttp
import argparse
import json
import toml
import yaml
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup
import re
import time

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select, WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
except ImportError:
    print("Please install selenium: pip install selenium")
    print("Also ensure you have Chrome/Chromium installed")
    exit(1)


class BillDiscovery:
    """Discovers bill numbers using Selenium."""

    def __init__(self, headless: bool = True):
        self.base_url = "https://web.senate.gov.ph/lis"
        self.headless = headless
        self.driver = None

    def setup_driver(self):
        """Setup Chrome driver with options."""
        options = webdriver.ChromeOptions()
        if self.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def close_driver(self):
        """Close the driver."""
        if self.driver:
            self.driver.quit()

    def switch_to_bill_type(self, bill_type: str) -> bool:
        """Switch dropdown to specified bill type."""
        try:
            print(f"    Switching to {bill_type} view...")

            dropdown_element = self.wait.until(
                EC.presence_of_element_located((By.NAME, 'dlBillType'))
            )

            dropdown = Select(dropdown_element)
            dropdown.select_by_value(bill_type)

            time.sleep(3)  # Wait for page to reload

            # Verify selection
            try:
                dropdown_element = self.driver.find_element(By.NAME, 'dlBillType')
                dropdown = Select(dropdown_element)
                selected = dropdown.first_selected_option.get_attribute('value')

                if selected == bill_type:
                    page_source = self.driver.page_source
                    if f'{bill_type}-' in page_source:
                        print(f"    ✓ {bill_type} bills are visible")
                        return True
                    else:
                        print(f"    ⚠️  {bill_type} selected but no bills visible")
                        return False
            except:
                return True  # Dropdown might not exist on some pages

        except Exception as e:
            print(f"    ❌ Error switching to {bill_type}: {e}")
            return False

    def sort_by_bill_number(self) -> bool:
        """Click on Bill No. link to sort by bill number."""
        try:
            print("    Sorting by Bill No...")
            bill_no_link = self.driver.find_element(By.ID, 'lbType')
            bill_no_link.click()
            time.sleep(3)
            print("    ✓ Sorted by Bill No.")
            return True
        except Exception as e:
            print(f"    ❌ Error sorting by Bill No.: {e}")
            return False

    def extract_bills_from_page(self) -> List[Tuple[str, int]]:
        """Extract bill types and numbers from current page."""
        bills = []

        try:
            bill_div = self.driver.find_element(By.CLASS_NAME, 'alight')
            bill_links = bill_div.find_elements(By.TAG_NAME, 'a')

            for link in bill_links:
                href = link.get_attribute('href')
                if href:
                    match = re.search(r'q=(SBN|HBN)-(\d+)', href)
                    if match:
                        bill_type = match.group(1)
                        bill_num = int(match.group(2))
                        bills.append((bill_type, bill_num))

        except Exception as e:
            print(f"    ❌ Error extracting bills: {e}")

        return bills

    def navigate_to_page(self, congress: int, bill_type: str, page_num: int) -> bool:
        """Navigate to a specific page number."""
        try:
            if page_num == 1:
                return True

            page_url = f'{self.base_url}/leg_sys.aspx?congress={congress}&type=bill&p={page_num}'
            self.driver.get(page_url)
            time.sleep(2)

            # Re-select bill type after navigation
            if bill_type == 'HBN':
                self.switch_to_bill_type(bill_type)

            return True

        except Exception as e:
            print(f"    ❌ Error navigating to page {page_num}: {e}")
            return False

    def discover_bills(self, congress: int, bill_type: str) -> List[int]:
        """Discover all bill numbers for a given congress and type."""
        print(f"\n  📋 Discovering {bill_type} bills for Congress {congress}")

        all_bills = set()

        try:
            # Load initial page
            url = f'{self.base_url}/leg_sys.aspx?congress={congress}&type=bill'
            print(f"    Loading {url}")
            self.driver.get(url)
            time.sleep(2)

            # Switch to correct bill type
            if bill_type == 'HBN':
                if not self.switch_to_bill_type(bill_type):
                    print(f"    ❌ Could not switch to {bill_type}")
                    return []

            # Sort by Bill No. to get complete listing
            self.sort_by_bill_number()

            # Process pages until we find no more
            page_num = 1
            consecutive_empty = 0
            max_pages = 500  # Safety limit

            while page_num <= max_pages:
                print(f"    Page {page_num}: ", end='')

                if page_num > 1:
                    if not self.navigate_to_page(congress, bill_type, page_num):
                        print("Could not navigate")
                        break

                # Extract bills from current page
                bills = self.extract_bills_from_page()
                page_bills = [num for typ, num in bills if typ == bill_type]

                if page_bills:
                    all_bills.update(page_bills)
                    print(f"{len(page_bills)} bills found")
                    consecutive_empty = 0

                    # Check if there's a next page
                    try:
                        self.driver.find_element(By.LINK_TEXT, 'Next')
                        page_num += 1
                    except:
                        print(f"\n    ✓ Reached last page")
                        break
                else:
                    print("No bills found")
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        print(f"    No bills on {consecutive_empty} consecutive pages, stopping")
                        break
                    page_num += 1

                time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"    ❌ Error discovering {bill_type} bills: {e}")

        sorted_bills = sorted(list(all_bills))

        if sorted_bills:
            print(f"    ✓ Total {bill_type} bills found: {len(sorted_bills)}")
            print(f"    Range: {bill_type}-{sorted_bills[0]} to {bill_type}-{sorted_bills[-1]}")

        return sorted_bills


class BillFetcher:
    """Fetches bill details using async HTTP."""

    def __init__(self, base_dir: str = ".", workers: int = 10):
        self.base_dir = Path(base_dir)
        self.base_url = "https://web.senate.gov.ph/lis"
        self.workers = workers
        self.session = None

    async def __aenter__(self):
        """Async context manager entry."""
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def clean_text(self, text: str) -> str:
        """Clean text by removing extra whitespace and fixing quotes."""
        if not text:
            return ""
        text = re.sub(r'\s+', ' ', text).strip()
        text = text.replace('"', "'")
        return text

    async def fetch_bill(self, congress: int, bill_type: str, number: int) -> Optional[Dict]:
        """Fetch a single bill's details with All Information view."""
        padded_num = str(number).zfill(5)
        base_url = f"{self.base_url}/bill_res.aspx?congress={congress}&q={bill_type}-{number}"

        try:
            # First fetch the page
            async with self.session.get(base_url) as response:
                if response.status != 200:
                    return None

                html = await response.text()

                # Check for server errors
                if "An error has occured" in html or "Exception has been logged" in html:
                    print(f"    ❌ {bill_type}-{number}: Server error on Senate website")
                    return {"error": "server_error", "bill": f"{bill_type}-{number}"}

                # Check if bill exists
                if "No results found" in html or "No Record Found" in html:
                    print(f"    ⚠️  {bill_type}-{number}: Not found on website")
                    return None

                # Check if it's the right congress
                if f"{congress}th Congress" not in html and f"{congress}TH CONGRESS" not in html:
                    # Try to find which congress it actually belongs to
                    actual_congress = None
                    for c in range(13, 21):  # Check congresses 13-20
                        if f"{c}th Congress" in html or f"{c}TH CONGRESS" in html:
                            actual_congress = c
                            break

                    if actual_congress:
                        print(f"    ⚠️  {bill_type}-{number}: Found in Congress {actual_congress}, not {congress}")
                    else:
                        print(f"    ⚠️  {bill_type}-{number}: Wrong congress (not {congress}th)")
                    return None

            # Check if we need to fetch "All Information" view
            if self.needs_all_information(html):
                # Extract form data for postback
                form_data = self.extract_all_info_form_data(html)
                if form_data:
                    # POST back to get All Information
                    async with self.session.post(base_url, data=form_data) as response:
                        if response.status == 200:
                            html = await response.text()

            # Now parse the page with all information
            soup = BeautifulSoup(html, 'html.parser')

            # Extract bill data
            bill_data = {
                'billNumber': f"{bill_type}-{padded_num}",
                'billType': bill_type,
                'congress': congress,
                'url': base_url,
                'lastScraped': datetime.now().isoformat()
            }

            # Extract title from h1_bold or lis_doctitle
            title_elem = soup.select_one('.lis_doctitle .h1_bold, .h1_bold')
            if title_elem:
                bill_data['title'] = self.clean_text(title_elem.get_text())

            # Extract author from "Filed on" text
            content_td = soup.find('td', id='content')
            if content_td:
                filed_text = content_td.get_text()
                filed_match = re.search(r'Filed on ([^\n]+) by ([^\n]+)', filed_text)
                if filed_match:
                    bill_data['filedDate'] = filed_match.group(1).strip()
                    bill_data['author'] = filed_match.group(2).strip()

            # Extract data from p/blockquote pairs
            paragraphs = soup.find_all('p')
            for p in paragraphs:
                p_text = self.clean_text(p.get_text()).lower()
                next_elem = p.find_next_sibling('blockquote')
                if next_elem:
                    content = self.clean_text(next_elem.get_text())

                    if 'long title' in p_text and content:
                        bill_data['longTitle'] = content
                    elif 'scope' in p_text and content:
                        bill_data['scope'] = content
                    elif 'subject' in p_text:
                        # Handle multiple subjects separated by <br> tags
                        # Get the raw HTML to preserve br tags
                        subjects = []
                        for br in next_elem.find_all('br'):
                            br.replace_with('|||')  # Replace br with delimiter
                        content = self.clean_text(next_elem.get_text())
                        if '|||' in content:
                            # Split by our delimiter
                            subjects = [s.strip() for s in content.split('|||') if s.strip()]
                        elif ';' in content or '/' in content:
                            # Fallback to semicolon or slash separation
                            subjects = re.split(r'[;/]', content)
                            subjects = [s.strip() for s in subjects if s.strip()]
                        else:
                            # Single subject
                            subjects = [content.strip()] if content.strip() else []

                        if subjects:
                            bill_data['subject'] = subjects
                    elif 'legislative status' in p_text and content:
                        # Extract status and date
                        status_match = re.match(r'(.+?)\s*\((\d+/\d+/\d+)\)', content)
                        if status_match:
                            bill_data['status'] = {
                                'status': status_match.group(1).strip(),
                                'date': status_match.group(2).strip()
                            }
                        else:
                            bill_data['status'] = {'status': content}
                    elif 'primary committee' in p_text and content:
                        bill_data['committee'] = {
                            'name': content,
                            'type': 'primary'
                        }

            # Extract abstract
            abstract_elem = soup.find('div', {'class': 'lis_billabstract'})
            if abstract_elem:
                bill_data['abstract'] = self.clean_text(abstract_elem.get_text())

            # Extract legislative history - PRIMARY SOURCE
            history = self.extract_legislative_history(soup)
            if history:
                bill_data['legislativeHistory'] = history

                # Extract additional info from history (e.g., co-authors)
                for entry in history:
                    action = entry.get('action', '')
                    # Check for introduced by senator (alternative author extraction)
                    if 'Introduced by Senator' in action and 'author' not in bill_data:
                        match = re.search(r'Introduced by Senator (.+?)(?:;|$)', action)
                        if match:
                            bill_data['author'] = match.group(1).strip()
                    # Extract co-authors
                    if 'Co-Author' in action:
                        match = re.search(r'Co-Authors?:\s*(.+)', action)
                        if match:
                            coauthors = match.group(1).strip()
                            bill_data['coAuthors'] = [a.strip() for a in coauthors.split(',')]

            # Extract related bills
            related = self.extract_related_bills(soup)
            if related:
                bill_data.update(related)

            # Extract PDF URL from download section
            download_div = soup.find('div', id='lis_download')
            if download_div:
                pdf_links = download_div.find_all('a', href=re.compile(r'\.pdf', re.I))
                if pdf_links:
                    pdf_url = pdf_links[0].get('href')
                    if not pdf_url.startswith('http'):
                        pdf_url = f"https://web.senate.gov.ph{pdf_url}"
                    bill_data['pdfUrl'] = pdf_url

                    # Get PDF info (filename, date, size)
                    pdf_text = pdf_links[0].get_text(strip=True)
                    if pdf_text:
                        bill_data['pdfFileName'] = pdf_text
            else:
                # Fallback: look for any PDF link
                pdf_link = soup.find('a', href=re.compile(r'\.pdf$', re.I))
                if pdf_link:
                    pdf_url = pdf_link.get('href')
                    if not pdf_url.startswith('http'):
                        pdf_url = f"https://web.senate.gov.ph{pdf_url}"
                    bill_data['pdfUrl'] = pdf_url

            return bill_data

        except asyncio.TimeoutError:
            print(f"    ⏱️  Timeout for {bill_type}-{number}")
            return None
        except Exception as e:
            print(f"    ❌ Error fetching {bill_type}-{number}: {str(e)[:100]}")
            return None

    def needs_all_information(self, html: str) -> bool:
        """Check if we need to click 'All Information' link."""
        soup = BeautifulSoup(html, 'html.parser')
        all_info_link = soup.find('a', {'id': 'lbAll'})
        if all_info_link:
            # If it doesn't have disabled attribute, we need to click it
            return not all_info_link.has_attr('disabled')
        return False

    def extract_all_info_form_data(self, html: str) -> Dict:
        """Extract ASP.NET form data for All Information postback."""
        soup = BeautifulSoup(html, 'html.parser')
        form_data = {}

        # Extract ViewState and other hidden fields
        viewstate = soup.find('input', {'id': '__VIEWSTATE'})
        if viewstate:
            form_data['__VIEWSTATE'] = viewstate.get('value', '')

        viewstate_gen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})
        if viewstate_gen:
            form_data['__VIEWSTATEGENERATOR'] = viewstate_gen.get('value', '')

        event_val = soup.find('input', {'id': '__EVENTVALIDATION'})
        if event_val:
            form_data['__EVENTVALIDATION'] = event_val.get('value', '')

        # Set event target for All Information
        form_data['__EVENTTARGET'] = 'lbAll'
        form_data['__EVENTARGUMENT'] = ''

        return form_data

    def extract_legislative_history(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract legislative history from bill page."""
        history = []

        # Look for Legislative History in blockquote with table
        for p in soup.find_all('p'):
            if 'legislative history' in p.get_text().lower():
                blockquote = p.find_next_sibling('blockquote')
                if blockquote:
                    table = blockquote.find('table', id='lis_table')
                    if table:
                        rows = table.find_all('tr')
                        for row in rows:
                            cells = row.find_all('td')

                            # Handle different row types
                            if len(cells) == 2:
                                # Date and action row
                                date_text = self.clean_text(cells[0].get_text())
                                action_text = self.clean_text(cells[1].get_text())

                                # Check if it's actually a date row (has date format)
                                if re.match(r'\d+/\d+/\d+', date_text):
                                    history.append({
                                        'date': date_text,
                                        'action': action_text
                                    })
                            elif len(cells) == 1 and cells[0].get('colspan') == '2':
                                # Full width row (like "Entitled:" or session info)
                                text = self.clean_text(cells[0].get_text())
                                if text and not text.startswith('['):
                                    # Add as special entry without date
                                    if 'Entitled:' in text:
                                        history.append({
                                            'date': '',
                                            'action': text
                                        })
                        break

        return history

    def extract_related_bills(self, soup: BeautifulSoup) -> Dict:
        """Extract related bills information."""
        related = {}

        # Look for consolidated bills
        consolidated_elem = soup.find('span', string=re.compile('Consolidated.*with'))
        if consolidated_elem:
            text = self.clean_text(consolidated_elem.get_text())
            match = re.findall(r'[SH]BN-\d+', text)
            if match:
                related['consolidatedWith'] = match

        # Look for substitute bills
        substitute_elem = soup.find('span', string=re.compile('In substitution'))
        if substitute_elem:
            text = self.clean_text(substitute_elem.get_text())
            match = re.findall(r'[SH]BN-\d+', text)
            if match:
                related['substituteFor'] = match

        # Look for related bills section
        related_section = soup.find('span', string=re.compile('Related.*Bill'))
        if related_section:
            text = self.clean_text(related_section.get_text())
            match = re.findall(r'[SH]BN-\d+', text)
            if match:
                related['relatedBills'] = match

        return related

    async def fetch_bills_batch(self, congress: int, bill_type: str, bill_numbers: List[int], update_index: bool = True) -> Tuple[int, int, List[str]]:
        """Fetch bills in batches and save to files."""
        print(f"\n  📊 Fetching {len(bill_numbers)} {bill_type} bills from Congress {congress}")

        # Show sample of bills to be fetched if list is small
        if len(bill_numbers) <= 30:
            print(f"    Bills to fetch: {', '.join([f'{bill_type}-{n}' for n in sorted(bill_numbers)[:10]])}")
            if len(bill_numbers) > 10:
                print(f"                    ... and {len(bill_numbers) - 10} more")

        # Create directory structure
        bill_dir = self.base_dir / "senate" / str(congress) / bill_type
        bill_dir.mkdir(parents=True, exist_ok=True)

        successful = 0
        failed = 0
        newly_fetched = 0
        server_errors = []

        # Process bills in batches
        for i in range(0, len(bill_numbers), self.workers):
            batch = bill_numbers[i:i + self.workers]
            tasks = [self.fetch_bill(congress, bill_type, num) for num in batch]
            results = await asyncio.gather(*tasks)

            for num, bill_data in zip(batch, results):
                if bill_data:
                    # Check if it's an error response
                    if isinstance(bill_data, dict) and bill_data.get("error") == "server_error":
                        server_errors.append(f"{bill_type}-{str(num).zfill(5)}")
                        failed += 1
                    else:
                        # Save individual bill file
                        padded_num = str(num).zfill(5)
                        bill_file = bill_dir / f"{bill_type}-{padded_num}.toml"

                        # Check if file already exists
                        if not bill_file.exists():
                            with open(bill_file, 'w', encoding='utf-8') as f:
                                toml.dump(bill_data, f)
                            successful += 1
                            newly_fetched += 1
                        else:
                            successful += 1  # Count as successful if already exists
                else:
                    failed += 1

            # Progress update
            total_processed = min(i + len(batch), len(bill_numbers))
            print(f"    Progress: {total_processed}/{len(bill_numbers)} bills processed")

            # Small delay between batches
            await asyncio.sleep(0.5)

        # Update index file if requested
        if update_index:
            update_index_file(self.base_dir, congress, bill_type)

        print(f"    ✓ Completed: {newly_fetched} newly fetched, {successful - newly_fetched} already existed, {failed} failed")

        # Report server errors if any
        if server_errors:
            print(f"    ⚠️  {len(server_errors)} bills have server errors on Senate website:")
            for bill in server_errors[:5]:  # Show first 5
                print(f"        - {bill}")
            if len(server_errors) > 5:
                print(f"        ... and {len(server_errors) - 5} more")

        return successful, failed, server_errors


def load_bill_cache(metadata_dir: Path, congress: int, bill_type: str) -> Optional[List[int]]:
    """Load bill numbers from cache file."""
    cache_file = metadata_dir / f"bills_congress_{congress}_{bill_type}.json"
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            data = json.load(f)
            return data.get('bills', [])
    return None


def save_bill_cache(metadata_dir: Path, congress: int, bill_type: str, bills: List[int]):
    """Save bill numbers to cache file."""
    metadata_dir.mkdir(parents=True, exist_ok=True)
    cache_file = metadata_dir / f"bills_congress_{congress}_{bill_type}.json"

    data = {
        'congress': congress,
        'type': bill_type,
        'count': len(bills),
        'bills': bills,
        'discovered': datetime.now().isoformat()
    }

    with open(cache_file, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"  💾 Saved {len(bills)} {bill_type} bills to cache: {cache_file}")


def get_missing_bills(metadata_dir: Path, congress: int, bill_type: str, base_dir: Path) -> List[int]:
    """Get list of bills that are in metadata but missing from disk."""
    # Load all expected bills from metadata
    cached_bills = load_bill_cache(metadata_dir, congress, bill_type)
    if not cached_bills:
        return []

    # Check which files already exist
    bill_dir = base_dir / "senate" / str(congress) / bill_type
    existing_bills = set()

    if bill_dir.exists():
        for bill_file in bill_dir.glob(f"{bill_type}-*.toml"):
            # Extract bill number from filename
            match = re.match(f"{bill_type}-(\\d+).toml", bill_file.name)
            if match:
                existing_bills.add(int(match.group(1)))

    # Return only missing bills
    missing_bills = [num for num in cached_bills if num not in existing_bills]

    print(f"  📁 Found {len(existing_bills)} existing files, {len(missing_bills)} missing files")

    # Show some examples of missing bills if there are any
    if missing_bills and len(missing_bills) <= 30:
        sample = sorted(missing_bills)[:10]
        print(f"      Missing: {', '.join([f'{bill_type}-{str(n).zfill(5)}' for n in sample])}")
        if len(missing_bills) > 10:
            print(f"      ... and {len(missing_bills) - 10} more")

    return missing_bills


def update_index_file(base_dir: Path, congress: int, bill_type: str):
    """Update or create index.yml file with all existing bills."""
    bill_dir = base_dir / "senate" / str(congress) / bill_type
    if not bill_dir.exists():
        return

    # Collect all existing bill files
    bills_data = []
    bill_numbers = []

    for bill_file in sorted(bill_dir.glob(f"{bill_type}-*.toml")):
        with open(bill_file, 'r', encoding='utf-8') as f:
            data = toml.load(f)
            bills_data.append(data)
            if 'billNumber' in data:
                bill_numbers.append(data['billNumber'])

    # Create/update index file
    if bills_data:
        index_file = bill_dir / "index.yml"
        index_data = {
            'congress': congress,
            'type': bill_type,
            'count': len(bills_data),
            'bills': bill_numbers,
            'generated': datetime.now().isoformat()
        }

        with open(index_file, 'w', encoding='utf-8') as f:
            yaml.dump(index_data, f, default_flow_style=False)

        print(f"    ✓ Updated index.yml with {len(bill_numbers)} bills")


async def extract_metadata(congresses: List[int], metadata_dir: Path, is_all_congresses: bool = False):
    """Extract metadata (senators, committees, statuses) for each congress."""
    print("\n📚 METADATA EXTRACTION")
    print("-" * 60)

    # Extract metadata for each congress separately
    metadata_by_congress = {}

    async with aiohttp.ClientSession() as session:
        for congress in congresses:
            print(f"  Extracting metadata from Congress {congress}...")
            url = f"https://web.senate.gov.ph/lis/leg_sys.aspx?congress={congress}&type=bill"

            congress_metadata = {
                'congress': congress,
                'extracted_at': datetime.now().isoformat(),
                'senators': {},
                'committees': {},
                'statuses': {}
            }

            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        # Extract senators
                        senator_select = soup.find('select', {'id': 'dlSenators'})
                        if senator_select:
                            for option in senator_select.find_all('option'):
                                value = option.get('value', '').strip()
                                text = option.get_text().strip()
                                if value and 'Author' not in text:
                                    congress_metadata['senators'][value] = {
                                        'code': value,
                                        'name': text,
                                        'full_name': text
                                    }

                        # Extract committees
                        committee_select = soup.find('select', {'id': 'dlCommittees'})
                        if committee_select:
                            for option in committee_select.find_all('option'):
                                value = option.get('value', '').strip()
                                text = option.get_text().strip()
                                if value and 'Primary committee' not in text:
                                    committee_type = 'regular'
                                    if 'Sub-Committee' in text or 'Subcommittee' in text:
                                        committee_type = 'subcommittee'
                                    elif 'Joint' in text or 'Jt. Cong.' in text:
                                        committee_type = 'joint'
                                    elif 'Special' in text:
                                        committee_type = 'special'
                                    elif 'Oversight' in text:
                                        committee_type = 'oversight'

                                    congress_metadata['committees'][value] = {
                                        'code': value,
                                        'name': text,
                                        'type': committee_type
                                    }

                        # Extract statuses
                        status_select = soup.find('select', {'id': 'dlStatus'})
                        if status_select:
                            for option in status_select.find_all('option'):
                                value = option.get('value', '').strip()
                                text = option.get_text().strip()
                                if value and 'Legislative status' not in text:
                                    stage = 0
                                    if '-' in value:
                                        parts = value.split('-')
                                        if parts[0].isdigit():
                                            stage = int(parts[0])

                                    congress_metadata['statuses'][value] = {
                                        'code': value,
                                        'name': text,
                                        'stage': stage
                                    }

                        print(f"    ✓ Found {len(congress_metadata['senators'])} senators")
                        print(f"    ✓ Found {len(congress_metadata['committees'])} committees")
                        print(f"    ✓ Found {len(congress_metadata['statuses'])} statuses")

                        metadata_by_congress[str(congress)] = congress_metadata

            except Exception as e:
                print(f"    ❌ Error extracting metadata for Congress {congress}: {e}")

    # Save metadata per congress in metadata_dir
    metadata_dir.mkdir(parents=True, exist_ok=True)

    for congress_str, metadata in metadata_by_congress.items():
        # Save individual congress metadata
        congress_file = metadata_dir / f"congress_{congress_str}.json"
        with open(congress_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        print(f"  ✅ Saved Congress {congress_str} metadata to {congress_file}")

    # Only save combined metadata file when extracting all congresses (13-20)
    if is_all_congresses and metadata_by_congress:
        combined_file = metadata_dir / 'all_congresses.json'
        combined_metadata = {
            'extracted_at': datetime.now().isoformat(),
            'congresses': metadata_by_congress
        }
        with open(combined_file, 'w', encoding='utf-8') as f:
            json.dump(combined_metadata, f, indent=2, ensure_ascii=False)
        print(f"\n  ✅ Combined metadata saved to {combined_file}")

    print(f"\n  📊 Summary:")
    for congress_str, metadata in metadata_by_congress.items():
        print(f"    Congress {congress_str}: {len(metadata['senators'])} senators, {len(metadata['committees'])} committees, {len(metadata['statuses'])} statuses")

    return metadata_by_congress


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Philippine Senate Bill Scraper')
    parser.add_argument('--congress', type=int, nargs='+', default=None,
                        help='Congress number(s) to scrape (default: all cached congresses)')
    parser.add_argument('--type', choices=['SBN', 'HBN', 'ALL'], default='ALL',
                        help='Type of bills to scrape')
    parser.add_argument('--discover', action='store_true',
                        help='Discover bill numbers and save to cache')
    parser.add_argument('--fetch', action='store_true',
                        help='Fetch bill details from cache')
    parser.add_argument('--metadata', action='store_true',
                        help='Extract metadata (senators, committees, statuses)')
    parser.add_argument('--workers', type=int, default=20,
                        help='Number of concurrent workers for fetching (default: 20)')
    parser.add_argument('--dir', type=str, default='.',
                        help='Base directory for output')
    parser.add_argument('--metadata-dir', type=str, default='metadata',
                        help='Directory for metadata and cache files')
    parser.add_argument('--headless', action='store_true', default=True,
                        help='Run browser in headless mode')
    parser.add_argument('--show-browser', action='store_true',
                        help='Show browser window (disables headless)')
    parser.add_argument('--force', action='store_true',
                        help='Force rediscovery even if cache exists')
    parser.add_argument('--skip-existing', action='store_true',
                        help='Only download missing files, skip existing ones')

    args = parser.parse_args()

    # Determine bill types
    if args.type == 'ALL':
        bill_types = ['SBN', 'HBN']
    else:
        bill_types = [args.type]

    # Setup paths
    metadata_dir = Path(args.metadata_dir)

    # If neither discover, fetch, nor metadata, do discover and fetch
    if not args.discover and not args.fetch and not args.metadata:
        args.discover = True
        args.fetch = True

    print("🚀 Philippine Senate Bill Scraper")
    print("=" * 60)

    # Metadata extraction phase
    if args.metadata:
        # If no congress specified or just default [19], extract all congresses (13-20)
        if args.congress == [19]:
            congresses = list(range(13, 21))  # Congress 13 to 20
            print(f"  📌 No specific congress provided, extracting metadata for congresses 13-20")
            is_all_congresses = True
        else:
            congresses = args.congress
            is_all_congresses = False
        await extract_metadata(congresses, metadata_dir, is_all_congresses)

    # Discovery phase
    if args.discover:
        print("\n📍 DISCOVERY PHASE")
        print("-" * 60)

        # For discovery, we need explicit congress numbers
        congresses_to_discover = args.congress
        if congresses_to_discover is None:
            congresses_to_discover = [19]  # Default to congress 19 for discovery
            print("  📌 No congress specified, defaulting to Congress 19")

        headless = args.headless and not args.show_browser
        discovery = BillDiscovery(headless=headless)
        discovery.setup_driver()

        try:
            for congress in congresses_to_discover:
                print(f"\n🏛️  Congress {congress}")

                for bill_type in bill_types:
                    # Check cache first
                    cached_bills = None
                    if not args.force:
                        cached_bills = load_bill_cache(metadata_dir, congress, bill_type)
                        if cached_bills:
                            print(f"  ✓ Using cached {bill_type} bills: {len(cached_bills)} bills")
                            continue

                    # Discover bills
                    bills = discovery.discover_bills(congress, bill_type)
                    if bills:
                        save_bill_cache(metadata_dir, congress, bill_type, bills)

        finally:
            discovery.close_driver()

    # Fetching phase
    if args.fetch:
        print("\n📥 FETCHING PHASE")
        print("-" * 60)

        # If no congress specified, detect from cached metadata
        congresses_to_fetch = args.congress
        if congresses_to_fetch is None:
            # Find all cached congress metadata files
            available_congresses = []
            for cache_file in metadata_dir.glob("bills_congress_*_*.json"):
                match = re.match(r"bills_congress_(\d+)_\w+\.json", cache_file.name)
                if match:
                    congress_num = int(match.group(1))
                    if congress_num not in available_congresses:
                        available_congresses.append(congress_num)

            if available_congresses:
                congresses_to_fetch = sorted(available_congresses)
                print(f"  📌 No congress specified, found cached data for congresses: {', '.join(map(str, congresses_to_fetch))}")
            else:
                print("  ⚠️  No cached congress data found. Run with --discover first.")
                congresses_to_fetch = []

        # Track all errors across congresses
        all_errors = {}

        async with BillFetcher(base_dir=args.dir, workers=args.workers) as fetcher:
            for congress in congresses_to_fetch:
                print(f"\n🏛️  Congress {congress}")
                congress_errors = {}

                for bill_type in bill_types:
                    # Load bills from cache
                    bills = load_bill_cache(metadata_dir, congress, bill_type)
                    if not bills:
                        print(f"  ⚠️  No cached {bill_type} bills found. Run with --discover first.")
                        continue

                    # Check for missing files if skip-existing is enabled
                    if args.skip_existing:
                        bills_to_fetch = get_missing_bills(metadata_dir, congress, bill_type, Path(args.dir))
                        if not bills_to_fetch:
                            print(f"  ✓ All {len(bills)} {bill_type} bills already exist")
                            # Update index file even if all files exist
                            update_index_file(Path(args.dir), congress, bill_type)
                            continue
                    else:
                        bills_to_fetch = bills

                    # Fetch bill details
                    successful, failed, server_errors = await fetcher.fetch_bills_batch(congress, bill_type, bills_to_fetch)

                    # Track errors for this congress
                    if server_errors:
                        congress_errors[bill_type] = server_errors

                if congress_errors:
                    all_errors[congress] = congress_errors

        # Display comprehensive error report
        if all_errors:
            print("\n" + "=" * 60)
            print("📋 ERROR REPORT - Bills with Senate Website Issues")
            print("=" * 60)

            total_errors = 0
            for congress in sorted(all_errors.keys()):
                congress_total = sum(len(errors) for errors in all_errors[congress].values())
                total_errors += congress_total

                print(f"\n🏛️  Congress {congress} ({congress_total} errors)")
                print("-" * 40)

                for bill_type in sorted(all_errors[congress].keys()):
                    errors = all_errors[congress][bill_type]
                    print(f"\n  {bill_type} Bills ({len(errors)} errors):")

                    # Group consecutive bill numbers for compact display
                    if errors:
                        # Sort and extract numbers
                        bill_nums = []
                        for bill in sorted(errors):
                            match = re.match(f"{bill_type}-(\\d+)", bill)
                            if match:
                                bill_nums.append(int(match.group(1)))

                        # Group consecutive numbers
                        if bill_nums:
                            ranges = []
                            start = bill_nums[0]
                            end = bill_nums[0]

                            for num in bill_nums[1:]:
                                if num == end + 1:
                                    end = num
                                else:
                                    if start == end:
                                        ranges.append(f"{bill_type}-{str(start).zfill(5)}")
                                    else:
                                        ranges.append(f"{bill_type}-{str(start).zfill(5)} to {str(end).zfill(5)}")
                                    start = num
                                    end = num

                            # Add the last range
                            if start == end:
                                ranges.append(f"{bill_type}-{str(start).zfill(5)}")
                            else:
                                ranges.append(f"{bill_type}-{str(start).zfill(5)} to {str(end).zfill(5)}")

                            # Display ranges
                            for i in range(0, len(ranges), 3):  # Show 3 per line
                                batch = ranges[i:i+3]
                                print(f"    {', '.join(batch)}")

            print(f"\n{'=' * 60}")
            print(f"Total bills with Senate website errors: {total_errors}")
            print(f"These bills appear in search but have broken detail pages.")
            print(f"This is a data issue on the Senate website, not a scraper problem.")
            print(f"{'=' * 60}")

            # Save error report to file
            error_report_file = metadata_dir / "senate_website_errors.json"
            error_report = {
                "generated": datetime.now().isoformat(),
                "total_errors": total_errors,
                "errors_by_congress": {}
            }

            for congress, congress_errors in all_errors.items():
                error_report["errors_by_congress"][str(congress)] = {
                    bill_type: sorted(errors) for bill_type, errors in congress_errors.items()
                }

            with open(error_report_file, 'w', encoding='utf-8') as f:
                json.dump(error_report, f, indent=2)

            print(f"\n📄 Error report saved to: {error_report_file}")

    print("\n✅ All operations completed!")


if __name__ == '__main__':
    asyncio.run(main())