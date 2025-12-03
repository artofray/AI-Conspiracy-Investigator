#!/usr/bin/env python3
"""
SHADOW FOIA Scraper System
Automated collection from major government and NGO FOIA libraries
"""

import os
import re
import json
import time
import hashlib
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Generator
from urllib.parse import urljoin, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
import logging
import sqlite3
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
CONFIG = {
    "download_dir": "foia_downloads",
    "max_concurrent_downloads": 5,
    "request_delay": 1.0,  # seconds between requests (be polite)
    "retry_attempts": 3,
    "user_agent": "SHADOW-Research-Bot/1.0 (Academic Research; Contact: research@example.com)",
    "database_path": "foia_scraper.db",
}

# ============ SOURCE DEFINITIONS ============
FOIA_SOURCES = {
    # ===== U.S. GOVERNMENT SOURCES =====
    "state_dept": {
        "name": "U.S. State Department FOIA Library",
        "base_url": "https://foia.state.gov/",
        "search_url": "https://foia.state.gov/Search/Search.aspx",
        "api_url": "https://foia.state.gov/api/search",
        "type": "government",
        "agency": "DOS",
        "description": "550k+ records including cables, correspondence, policy documents",
        "document_count_estimate": 550000,
        "formats": ["pdf", "html"],
        "scraper_class": "StateDeptScraper",
    },
    
    "fbi_vault": {
        "name": "FBI Vault FOIA Library",
        "base_url": "https://vault.fbi.gov/",
        "type": "government",
        "agency": "FBI",
        "description": "Thousands of topic-organized FOIA releases on intel, organized crime, political movements",
        "document_count_estimate": 10000,
        "formats": ["pdf"],
        "scraper_class": "FBIVaultScraper",
    },
    
    "cia_foia": {
        "name": "CIA FOIA Reading Room",
        "base_url": "https://www.cia.gov/readingroom/",
        "search_url": "https://www.cia.gov/readingroom/search/site/",
        "type": "government",
        "agency": "CIA",
        "description": "Declassified intelligence reports and analyses",
        "document_count_estimate": 100000,
        "formats": ["pdf"],
        "scraper_class": "CIAFOIAScraper",
    },
    
    "cia_crest": {
        "name": "CIA CREST Database",
        "base_url": "https://www.cia.gov/readingroom/collection/crest-25-year-program-archive",
        "type": "government",
        "agency": "CIA",
        "description": "Tens of millions of pages of declassified historical files",
        "document_count_estimate": 13000000,
        "formats": ["pdf", "tiff"],
        "scraper_class": "CRESTScraper",
    },
    
    "doe_opennet": {
        "name": "DOE OpenNet",
        "base_url": "https://www.osti.gov/opennet/",
        "search_url": "https://www.osti.gov/opennet/advancedsearch",
        "type": "government",
        "agency": "DOE",
        "description": "150k+ declassified documents on nuclear, energy tech, and national security R&D",
        "document_count_estimate": 150000,
        "formats": ["pdf"],
        "scraper_class": "DOEOpenNetScraper",
    },
    
    "nara_jfk": {
        "name": "National Archives JFK Assassination Records",
        "base_url": "https://www.archives.gov/research/jfk",
        "catalog_url": "https://catalog.archives.gov/",
        "type": "government",
        "agency": "NARA",
        "description": "JFK assassination records collection",
        "document_count_estimate": 50000,
        "formats": ["pdf", "tiff"],
        "scraper_class": "NARAScraper",
    },
    
    "epa_foia": {
        "name": "EPA FOIA Library",
        "base_url": "https://foiaonline.gov/foiaonline/action/public/search",
        "type": "government",
        "agency": "EPA",
        "description": "Environmental risk files, regulatory enforcement, industry interactions",
        "document_count_estimate": 50000,
        "formats": ["pdf"],
        "scraper_class": "EPAScraper",
    },
    
    "dod_foia": {
        "name": "DoD FOIA Reading Room",
        "base_url": "https://open.defense.gov/",
        "type": "government",
        "agency": "DOD",
        "description": "Defense Department declassified records",
        "document_count_estimate": 25000,
        "formats": ["pdf"],
        "scraper_class": "DODScraper",
    },
    
    # ===== NON-GOVERNMENT AGGREGATORS =====
    "nsarchive": {
        "name": "National Security Archive",
        "base_url": "https://nsarchive.gwu.edu/",
        "type": "ngo",
        "description": "Massive NGO collection of declassified docs via FOIA and MDR",
        "document_count_estimate": 200000,
        "formats": ["pdf"],
        "scraper_class": "NSArchiveScraper",
    },
    
    "muckrock": {
        "name": "MuckRock FOIA Archive",
        "base_url": "https://www.muckrock.com/",
        "api_url": "https://www.muckrock.com/api_v1/",
        "type": "ngo",
        "description": "Crowdsourced FOIA requests and responses",
        "document_count_estimate": 100000,
        "formats": ["pdf", "html"],
        "scraper_class": "MuckRockScraper",
    },
    
    "governmentattic": {
        "name": "GovernmentAttic.org",
        "base_url": "https://www.governmentattic.org/",
        "type": "ngo",
        "description": "Large collection of FOIA-obtained government documents",
        "document_count_estimate": 50000,
        "formats": ["pdf"],
        "scraper_class": "GovernmentAtticScraper",
    },
    
    "archive_org_foia": {
        "name": "Internet Archive FOIA Collection",
        "base_url": "https://archive.org/details/foia",
        "api_url": "https://archive.org/advancedsearch.php",
        "type": "archive",
        "description": "FOIA documents archived on Internet Archive",
        "document_count_estimate": 100000,
        "formats": ["pdf", "html"],
        "scraper_class": "InternetArchiveScraper",
    },
    
    # ===== FOIA METADATA SOURCES =====
    "foia_gov": {
        "name": "FOIA.gov Dataset Downloads",
        "base_url": "https://www.foia.gov/",
        "data_url": "https://www.foia.gov/data.html",
        "type": "metadata",
        "description": "Bulk XML/CSV datasets of FOIA logs and processing metrics by agency since 2008",
        "document_count_estimate": 1000000,
        "formats": ["xml", "csv", "json"],
        "scraper_class": "FOIAGovMetaScraper",
    },
}

# ============ DATA MODELS ============
@dataclass
class FOIADocument:
    """Represents a FOIA document"""
    id: str
    source_id: str
    title: str
    url: str
    local_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_size: Optional[int] = None
    file_type: str = "pdf"
    
    # Metadata
    agency: Optional[str] = None
    date_released: Optional[str] = None
    date_created: Optional[str] = None
    case_number: Optional[str] = None
    subject: Optional[str] = None
    description: Optional[str] = None
    classification: Optional[str] = None
    pages: Optional[int] = None
    
    # Processing status
    downloaded: bool = False
    processed: bool = False
    error: Optional[str] = None
    
    # Timestamps
    discovered_at: str = None
    downloaded_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.discovered_at:
            self.discovered_at = datetime.now().isoformat()


@dataclass
class ScraperProgress:
    """Tracks scraper progress for resumability"""
    source_id: str
    last_page: int = 0
    last_document_id: Optional[str] = None
    total_discovered: int = 0
    total_downloaded: int = 0
    total_errors: int = 0
    started_at: str = None
    updated_at: str = None
    completed: bool = False


# ============ DATABASE SETUP ============
def init_scraper_db(db_path: str) -> sqlite3.Connection:
    """Initialize scraper tracking database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS foia_documents (
            id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            title TEXT,
            url TEXT NOT NULL,
            local_path TEXT,
            file_hash TEXT,
            file_size INTEGER,
            file_type TEXT,
            agency TEXT,
            date_released TEXT,
            date_created TEXT,
            case_number TEXT,
            subject TEXT,
            description TEXT,
            classification TEXT,
            pages INTEGER,
            downloaded INTEGER DEFAULT 0,
            processed INTEGER DEFAULT 0,
            error TEXT,
            discovered_at TEXT,
            downloaded_at TEXT,
            metadata TEXT
        )
    """)
    
    # Progress tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scraper_progress (
            source_id TEXT PRIMARY KEY,
            last_page INTEGER DEFAULT 0,
            last_document_id TEXT,
            total_discovered INTEGER DEFAULT 0,
            total_downloaded INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            started_at TEXT,
            updated_at TEXT,
            completed INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)
    
    # Download queue
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_queue (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            attempts INTEGER DEFAULT 0,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            error TEXT,
            FOREIGN KEY (document_id) REFERENCES foia_documents(id)
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_source ON foia_documents(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_downloaded ON foia_documents(downloaded)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_queue_status ON download_queue(status)")
    
    conn.commit()
    return conn


# ============ BASE SCRAPER CLASS ============
class BaseFOIAScraper:
    """Base class for FOIA scrapers"""
    
    def __init__(self, source_id: str, config: Dict, db_conn: sqlite3.Connection):
        self.source_id = source_id
        self.source_config = FOIA_SOURCES[source_id]
        self.config = config
        self.conn = db_conn
        self.session = None
        
        # Create download directory
        self.download_dir = Path(config["download_dir"]) / source_id
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
    async def init_session(self):
        """Initialize aiohttp session"""
        if not self.session:
            timeout = aiohttp.ClientTimeout(total=60)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.config["user_agent"]}
            )
    
    async def close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def fetch_page(self, url: str, params: Dict = None) -> Optional[str]:
        """Fetch a page with retry logic"""
        await self.init_session()
        
        for attempt in range(self.config["retry_attempts"]):
            try:
                await asyncio.sleep(self.config["request_delay"])
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        return await response.text()
                    elif response.status == 429:  # Rate limited
                        wait_time = int(response.headers.get("Retry-After", 60))
                        logger.warning(f"Rate limited, waiting {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.warning(f"HTTP {response.status} for {url}")
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def download_file(self, url: str, local_path: Path) -> bool:
        """Download a file"""
        await self.init_session()
        
        try:
            await asyncio.sleep(self.config["request_delay"])
            async with self.session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            await f.write(chunk)
                    return True
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
        
        return False
    
    def save_document(self, doc: FOIADocument):
        """Save document to database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO foia_documents (
                id, source_id, title, url, local_path, file_hash, file_size,
                file_type, agency, date_released, date_created, case_number,
                subject, description, classification, pages, downloaded,
                processed, error, discovered_at, downloaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc.id, doc.source_id, doc.title, doc.url, doc.local_path,
            doc.file_hash, doc.file_size, doc.file_type, doc.agency,
            doc.date_released, doc.date_created, doc.case_number,
            doc.subject, doc.description, doc.classification, doc.pages,
            1 if doc.downloaded else 0, 1 if doc.processed else 0,
            doc.error, doc.discovered_at, doc.downloaded_at
        ))
        self.conn.commit()
    
    def get_progress(self) -> ScraperProgress:
        """Get or create progress record"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM scraper_progress WHERE source_id = ?", (self.source_id,))
        row = cursor.fetchone()
        
        if row:
            return ScraperProgress(
                source_id=row["source_id"],
                last_page=row["last_page"],
                last_document_id=row["last_document_id"],
                total_discovered=row["total_discovered"],
                total_downloaded=row["total_downloaded"],
                total_errors=row["total_errors"],
                started_at=row["started_at"],
                updated_at=row["updated_at"],
                completed=bool(row["completed"])
            )
        else:
            progress = ScraperProgress(
                source_id=self.source_id,
                started_at=datetime.now().isoformat()
            )
            self.save_progress(progress)
            return progress
    
    def save_progress(self, progress: ScraperProgress):
        """Save progress to database"""
        progress.updated_at = datetime.now().isoformat()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO scraper_progress (
                source_id, last_page, last_document_id, total_discovered,
                total_downloaded, total_errors, started_at, updated_at, completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            progress.source_id, progress.last_page, progress.last_document_id,
            progress.total_discovered, progress.total_downloaded, progress.total_errors,
            progress.started_at, progress.updated_at, 1 if progress.completed else 0
        ))
        self.conn.commit()
    
    async def discover_documents(self) -> Generator[FOIADocument, None, None]:
        """Override in subclass to discover documents"""
        raise NotImplementedError
    
    async def run(self, download: bool = True, max_documents: int = None):
        """Run the scraper"""
        progress = self.get_progress()
        logger.info(f"Starting scraper for {self.source_config['name']}")
        logger.info(f"Progress: {progress.total_discovered} discovered, {progress.total_downloaded} downloaded")
        
        try:
            count = 0
            async for doc in self.discover_documents():
                self.save_document(doc)
                progress.total_discovered += 1
                progress.last_document_id = doc.id
                
                if download and not doc.downloaded:
                    local_path = self.download_dir / f"{doc.id}.{doc.file_type}"
                    if await self.download_file(doc.url, local_path):
                        doc.local_path = str(local_path)
                        doc.downloaded = True
                        doc.downloaded_at = datetime.now().isoformat()
                        doc.file_size = local_path.stat().st_size
                        progress.total_downloaded += 1
                        self.save_document(doc)
                        logger.info(f"Downloaded: {doc.title[:50]}...")
                    else:
                        progress.total_errors += 1
                
                count += 1
                if count % 10 == 0:
                    self.save_progress(progress)
                
                if max_documents and count >= max_documents:
                    break
            
            progress.completed = True
            self.save_progress(progress)
            logger.info(f"Completed: {progress.total_discovered} documents, {progress.total_downloaded} downloaded")
            
        finally:
            await self.close_session()


# ============ FBI VAULT SCRAPER ============
class FBIVaultScraper(BaseFOIAScraper):
    """Scraper for FBI Vault"""
    
    async def get_categories(self) -> List[Dict]:
        """Get all category pages from FBI Vault"""
        categories = []
        html = await self.fetch_page(self.source_config["base_url"])
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            # Find category links
            for link in soup.select('a[href*="/vault/"]'):
                href = link.get('href', '')
                if href and '/vault/' in href and href != '/vault/':
                    categories.append({
                        "name": link.get_text(strip=True),
                        "url": urljoin(self.source_config["base_url"], href)
                    })
        
        return categories
    
    async def get_documents_from_category(self, category_url: str) -> List[FOIADocument]:
        """Extract documents from a category page"""
        documents = []
        html = await self.fetch_page(category_url)
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find PDF links
            for link in soup.select('a[href$=".pdf"]'):
                href = link.get('href', '')
                if href:
                    url = urljoin(category_url, href)
                    doc_id = hashlib.md5(url.encode()).hexdigest()[:16]
                    
                    documents.append(FOIADocument(
                        id=doc_id,
                        source_id=self.source_id,
                        title=link.get_text(strip=True) or Path(href).stem,
                        url=url,
                        file_type="pdf",
                        agency="FBI"
                    ))
        
        return documents
    
    async def discover_documents(self):
        """Discover all FBI Vault documents"""
        categories = await self.get_categories()
        logger.info(f"Found {len(categories)} categories")
        
        for category in categories:
            logger.info(f"Processing category: {category['name']}")
            documents = await self.get_documents_from_category(category["url"])
            
            for doc in documents:
                doc.subject = category["name"]
                yield doc


# ============ STATE DEPARTMENT SCRAPER ============
class StateDeptScraper(BaseFOIAScraper):
    """Scraper for State Department FOIA Library"""
    
    async def search_documents(self, query: str = "*", start: int = 0, rows: int = 100) -> Dict:
        """Search State Dept FOIA API"""
        # Note: State Dept uses a Solr-like API
        params = {
            "searchText": query,
            "beginDate": "",
            "endDate": "",
            "collectionMatch": "false",
            "postedBeginDate": "",
            "postedEndDate": "",
            "caseNumber": "",
            "start": start,
            "rows": rows
        }
        
        try:
            response = requests.get(
                self.source_config["api_url"],
                params=params,
                headers={"User-Agent": self.config["user_agent"]},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"State Dept API error: {e}")
        
        return {}
    
    async def discover_documents(self):
        """Discover State Dept documents"""
        progress = self.get_progress()
        start = progress.last_page * 100
        
        while True:
            results = await self.search_documents(start=start)
            
            if not results or "Results" not in results:
                break
            
            docs = results.get("Results", [])
            if not docs:
                break
            
            for item in docs:
                doc_id = item.get("pdfLink", "").split("/")[-1].replace(".pdf", "")
                if not doc_id:
                    doc_id = hashlib.md5(str(item).encode()).hexdigest()[:16]
                
                pdf_url = item.get("pdfLink", "")
                if not pdf_url.startswith("http"):
                    pdf_url = urljoin(self.source_config["base_url"], pdf_url)
                
                yield FOIADocument(
                    id=doc_id,
                    source_id=self.source_id,
                    title=item.get("subject", "Untitled"),
                    url=pdf_url,
                    file_type="pdf",
                    agency="DOS",
                    date_released=item.get("postedDate"),
                    date_created=item.get("docDate"),
                    case_number=item.get("caseNumber"),
                    subject=item.get("subject"),
                    description=item.get("messageNumber"),
                    pages=item.get("totalPages")
                )
            
            start += 100
            progress.last_page = start // 100
            self.save_progress(progress)


# ============ CIA FOIA SCRAPER ============
class CIAFOIAScraper(BaseFOIAScraper):
    """Scraper for CIA FOIA Reading Room"""
    
    async def get_collections(self) -> List[Dict]:
        """Get available collections"""
        collections = []
        html = await self.fetch_page(self.source_config["base_url"])
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.select('a[href*="/collection/"]'):
                href = link.get('href', '')
                if href:
                    collections.append({
                        "name": link.get_text(strip=True),
                        "url": urljoin(self.source_config["base_url"], href)
                    })
        
        return collections
    
    async def search_collection(self, collection_url: str, page: int = 0) -> List[FOIADocument]:
        """Search within a collection"""
        documents = []
        url = f"{collection_url}?page={page}"
        html = await self.fetch_page(url)
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            
            for item in soup.select('.document-item, .views-row'):
                link = item.select_one('a[href*="/document/"]')
                if link:
                    doc_url = urljoin(collection_url, link.get('href', ''))
                    doc_id = doc_url.split('/')[-1] or hashlib.md5(doc_url.encode()).hexdigest()[:16]
                    
                    title = link.get_text(strip=True)
                    date_elem = item.select_one('.date, .field-content')
                    date = date_elem.get_text(strip=True) if date_elem else None
                    
                    documents.append(FOIADocument(
                        id=doc_id,
                        source_id=self.source_id,
                        title=title,
                        url=doc_url,
                        file_type="pdf",
                        agency="CIA",
                        date_released=date
                    ))
        
        return documents
    
    async def discover_documents(self):
        """Discover CIA FOIA documents"""
        collections = await self.get_collections()
        logger.info(f"Found {len(collections)} collections")
        
        for collection in collections:
            logger.info(f"Processing: {collection['name']}")
            page = 0
            
            while True:
                documents = await self.search_collection(collection["url"], page)
                if not documents:
                    break
                
                for doc in documents:
                    doc.subject = collection["name"]
                    yield doc
                
                page += 1
                if page > 100:  # Safety limit
                    break


# ============ NATIONAL SECURITY ARCHIVE SCRAPER ============
class NSArchiveScraper(BaseFOIAScraper):
    """Scraper for National Security Archive"""
    
    async def get_briefing_books(self) -> List[Dict]:
        """Get all briefing books/topics"""
        books = []
        html = await self.fetch_page(self.source_config["base_url"] + "briefing-books")
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.select('a[href*="/briefing-book/"]'):
                href = link.get('href', '')
                if href:
                    books.append({
                        "name": link.get_text(strip=True),
                        "url": urljoin(self.source_config["base_url"], href)
                    })
        
        return books
    
    async def get_documents_from_book(self, book_url: str) -> List[FOIADocument]:
        """Extract documents from a briefing book"""
        documents = []
        html = await self.fetch_page(book_url)
        
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            
            for link in soup.select('a[href$=".pdf"]'):
                href = link.get('href', '')
                if href:
                    url = urljoin(book_url, href)
                    doc_id = hashlib.md5(url.encode()).hexdigest()[:16]
                    
                    documents.append(FOIADocument(
                        id=doc_id,
                        source_id=self.source_id,
                        title=link.get_text(strip=True) or Path(href).stem,
                        url=url,
                        file_type="pdf"
                    ))
        
        return documents
    
    async def discover_documents(self):
        """Discover NSArchive documents"""
        books = await self.get_briefing_books()
        logger.info(f"Found {len(books)} briefing books")
        
        for book in books:
            logger.info(f"Processing: {book['name']}")
            documents = await self.get_documents_from_book(book["url"])
            
            for doc in documents:
                doc.subject = book["name"]
                yield doc


# ============ INTERNET ARCHIVE SCRAPER ============
class InternetArchiveScraper(BaseFOIAScraper):
    """Scraper for Internet Archive FOIA collections"""
    
    async def search_archive(self, query: str = "foia", page: int = 1) -> Dict:
        """Search Internet Archive"""
        params = {
            "q": f"collection:(foia) OR subject:(foia) {query}",
            "fl[]": ["identifier", "title", "description", "date", "mediatype"],
            "sort[]": "date desc",
            "rows": 100,
            "page": page,
            "output": "json"
        }
        
        try:
            response = requests.get(
                self.source_config["api_url"],
                params=params,
                headers={"User-Agent": self.config["user_agent"]},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Internet Archive API error: {e}")
        
        return {}
    
    async def get_item_files(self, identifier: str) -> List[Dict]:
        """Get files for an Internet Archive item"""
        url = f"https://archive.org/metadata/{identifier}/files"
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.json().get("result", [])
        except Exception as e:
            logger.error(f"Error getting files for {identifier}: {e}")
        
        return []
    
    async def discover_documents(self):
        """Discover Internet Archive FOIA documents"""
        page = 1
        
        while True:
            results = await self.search_archive(page=page)
            
            if not results or "response" not in results:
                break
            
            docs = results["response"].get("docs", [])
            if not docs:
                break
            
            for item in docs:
                identifier = item.get("identifier", "")
                if not identifier:
                    continue
                
                # Get PDF files from this item
                files = await self.get_item_files(identifier)
                
                for file_info in files:
                    if file_info.get("format") == "PDF" or file_info.get("name", "").endswith(".pdf"):
                        file_name = file_info.get("name", "")
                        url = f"https://archive.org/download/{identifier}/{file_name}"
                        doc_id = hashlib.md5(url.encode()).hexdigest()[:16]
                        
                        yield FOIADocument(
                            id=doc_id,
                            source_id=self.source_id,
                            title=item.get("title", file_name),
                            url=url,
                            file_type="pdf",
                            description=item.get("description"),
                            date_created=item.get("date")
                        )
            
            page += 1
            if page > 100:  # Safety limit
                break


# ============ MUCKROCK SCRAPER ============
class MuckRockScraper(BaseFOIAScraper):
    """Scraper for MuckRock FOIA Archive"""
    
    async def search_requests(self, page: int = 1) -> Dict:
        """Search MuckRock requests"""
        params = {
            "page": page,
            "per_page": 100,
            "status": "done"  # Only completed requests
        }
        
        try:
            response = requests.get(
                f"{self.source_config['api_url']}foia/",
                params=params,
                headers={"User-Agent": self.config["user_agent"]},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"MuckRock API error: {e}")
        
        return {}
    
    async def discover_documents(self):
        """Discover MuckRock documents"""
        page = 1
        
        while True:
            results = await self.search_requests(page=page)
            
            if not results or "results" not in results:
                break
            
            requests_list = results.get("results", [])
            if not requests_list:
                break
            
            for request in requests_list:
                # Each request can have multiple files
                files = request.get("communications", [])
                
                for comm in files:
                    for file_info in comm.get("files", []):
                        url = file_info.get("ffile", "")
                        if url and url.endswith(".pdf"):
                            doc_id = hashlib.md5(url.encode()).hexdigest()[:16]
                            
                            yield FOIADocument(
                                id=doc_id,
                                source_id=self.source_id,
                                title=file_info.get("title", request.get("title", "Untitled")),
                                url=url,
                                file_type="pdf",
                                agency=request.get("agency", {}).get("name"),
                                date_released=comm.get("date"),
                                subject=request.get("title"),
                                description=request.get("description")
                            )
            
            page += 1
            if not results.get("next"):
                break


# ============ SCRAPER FACTORY ============
def get_scraper(source_id: str, config: Dict = None, db_conn: sqlite3.Connection = None) -> BaseFOIAScraper:
    """Get appropriate scraper for a source"""
    if config is None:
        config = CONFIG
    
    if db_conn is None:
        db_conn = init_scraper_db(config["database_path"])
    
    scraper_classes = {
        "fbi_vault": FBIVaultScraper,
        "state_dept": StateDeptScraper,
        "cia_foia": CIAFOIAScraper,
        "nsarchive": NSArchiveScraper,
        "archive_org_foia": InternetArchiveScraper,
        "muckrock": MuckRockScraper,
    }
    
    scraper_class = scraper_classes.get(source_id, BaseFOIAScraper)
    return scraper_class(source_id, config, db_conn)


# ============ CLI ============
async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SHADOW FOIA Scraper")
    subparsers = parser.add_subparsers(dest='command')
    
    # List sources
    list_parser = subparsers.add_parser('list', help='List available sources')
    
    # Scrape command
    scrape_parser = subparsers.add_parser('scrape', help='Scrape a source')
    scrape_parser.add_argument('source', help='Source ID to scrape')
    scrape_parser.add_argument('--no-download', action='store_true', help='Discover only, do not download')
    scrape_parser.add_argument('--max', type=int, help='Maximum documents to process')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show scraper status')
    status_parser.add_argument('--source', help='Specific source to check')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download pending documents')
    download_parser.add_argument('source', help='Source ID')
    download_parser.add_argument('--max', type=int, default=100, help='Max documents to download')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        print("\n=== Available FOIA Sources ===\n")
        for source_id, source in FOIA_SOURCES.items():
            print(f"{source_id}:")
            print(f"  Name: {source['name']}")
            print(f"  Type: {source['type']}")
            print(f"  Est. Documents: {source.get('document_count_estimate', 'Unknown'):,}")
            print(f"  URL: {source['base_url']}")
            print()
    
    elif args.command == 'scrape':
        if args.source not in FOIA_SOURCES:
            print(f"Unknown source: {args.source}")
            print(f"Available: {', '.join(FOIA_SOURCES.keys())}")
            return
        
        scraper = get_scraper(args.source)
        await scraper.run(
            download=not args.no_download,
            max_documents=args.max
        )
    
    elif args.command == 'status':
        conn = init_scraper_db(CONFIG["database_path"])
        cursor = conn.cursor()
        
        if args.source:
            cursor.execute("SELECT * FROM scraper_progress WHERE source_id = ?", (args.source,))
            row = cursor.fetchone()
            if row:
                print(f"\n=== {args.source} ===")
                print(f"Discovered: {row['total_discovered']}")
                print(f"Downloaded: {row['total_downloaded']}")
                print(f"Errors: {row['total_errors']}")
                print(f"Completed: {'Yes' if row['completed'] else 'No'}")
                print(f"Last Updated: {row['updated_at']}")
        else:
            print("\n=== All Sources Status ===\n")
            cursor.execute("SELECT * FROM scraper_progress")
            for row in cursor.fetchall():
                print(f"{row['source_id']}: {row['total_discovered']} discovered, {row['total_downloaded']} downloaded")
    
    elif args.command == 'download':
        scraper = get_scraper(args.source)
        
        cursor = scraper.conn.cursor()
        cursor.execute("""
            SELECT * FROM foia_documents 
            WHERE source_id = ? AND downloaded = 0
            LIMIT ?
        """, (args.source, args.max))
        
        for row in cursor.fetchall():
            doc = FOIADocument(
                id=row["id"],
                source_id=row["source_id"],
                title=row["title"],
                url=row["url"],
                file_type=row["file_type"] or "pdf"
            )
            
            local_path = scraper.download_dir / f"{doc.id}.{doc.file_type}"
            if await scraper.download_file(doc.url, local_path):
                doc.local_path = str(local_path)
                doc.downloaded = True
                doc.downloaded_at = datetime.now().isoformat()
                doc.file_size = local_path.stat().st_size
                scraper.save_document(doc)
                print(f"Downloaded: {doc.title[:50]}...")
        
        await scraper.close_session()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
