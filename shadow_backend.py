#!/usr/bin/env python3
"""
SHADOW Investigation Platform - Backend Document Processor
Processes FOIA releases, Epstein files, and other document dumps
Builds a searchable knowledge base with AI-powered classification
"""

import os
import sys
import json
import sqlite3
import hashlib
import zipfile
import tarfile
import requests
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
CONFIG = {
    "database_path": "shadow_knowledge.db",
    "documents_dir": "documents",
    "processed_dir": "processed",
    "embeddings_dir": "embeddings",
    "chunk_size": 2000,  # characters per chunk
    "chunk_overlap": 200,
    "max_workers": 4,
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),  # For embeddings
}

# Known document sources
SOURCES = {
    "epstein_oversight": {
        "name": "House Oversight Epstein Documents",
        "url": "https://oversight.house.gov/release/comer-releases-additional-epstein-documents/",
        "type": "congressional_release",
        "description": "House Oversight Committee Epstein estate document release"
    },
    "cia_foia": {
        "name": "CIA FOIA Reading Room",
        "url": "https://www.cia.gov/readingroom/",
        "type": "foia",
        "description": "CIA Freedom of Information Act releases"
    },
    "fbi_vault": {
        "name": "FBI Vault",
        "url": "https://vault.fbi.gov/",
        "type": "foia",
        "description": "FBI FOIA document releases"
    },
    "jfk_files": {
        "name": "JFK Assassination Records",
        "url": "https://www.archives.gov/research/jfk",
        "type": "declassified",
        "description": "National Archives JFK files"
    }
}

# ============ DATA MODELS ============
@dataclass
class Document:
    id: str
    source_id: str
    file_path: str
    file_name: str
    file_type: str
    file_size: int
    file_hash: str
    created_at: str
    processed_at: Optional[str] = None
    ocr_text: Optional[str] = None
    metadata: Optional[Dict] = None

@dataclass
class Chunk:
    id: str
    document_id: str
    chunk_index: int
    content: str
    start_char: int
    end_char: int
    classification: Optional[str] = None
    relevance_score: Optional[float] = None
    entities: Optional[List[Dict]] = None

@dataclass
class Entity:
    id: str
    name: str
    entity_type: str  # person, organization, location, date, money, event
    aliases: List[str]
    first_seen: str
    last_seen: str
    mention_count: int
    metadata: Optional[Dict] = None

@dataclass
class Relationship:
    id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    evidence_chunks: List[str]
    confidence: float
    first_seen: str
    metadata: Optional[Dict] = None

# ============ DATABASE SETUP ============
def init_database(db_path: str) -> sqlite3.Connection:
    """Initialize SQLite database with full schema"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # Sources table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT,
            source_type TEXT,
            description TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT,
            document_count INTEGER DEFAULT 0,
            metadata TEXT
        )
    """)
    
    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            source_id TEXT,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_type TEXT,
            file_size INTEGER,
            file_hash TEXT UNIQUE,
            created_at TEXT,
            processed_at TEXT,
            ocr_text TEXT,
            page_count INTEGER,
            has_images INTEGER DEFAULT 0,
            is_redacted INTEGER DEFAULT 0,
            classification TEXT,
            relevance_score REAL,
            metadata TEXT,
            FOREIGN KEY (source_id) REFERENCES sources(id)
        )
    """)
    
    # Chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER,
            content TEXT NOT NULL,
            start_char INTEGER,
            end_char INTEGER,
            classification TEXT,
            relevance_score REAL,
            entities TEXT,
            embedding BLOB,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    
    # Entities table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            normalized_name TEXT,
            aliases TEXT,
            first_seen TEXT,
            last_seen TEXT,
            mention_count INTEGER DEFAULT 0,
            importance_score REAL,
            metadata TEXT,
            UNIQUE(normalized_name, entity_type)
        )
    """)
    
    # Entity mentions table (links entities to chunks)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entity_mentions (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            context TEXT,
            confidence REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (entity_id) REFERENCES entities(id),
            FOREIGN KEY (chunk_id) REFERENCES chunks(id),
            FOREIGN KEY (document_id) REFERENCES documents(id)
        )
    """)
    
    # Relationships table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            id TEXT PRIMARY KEY,
            source_entity_id TEXT NOT NULL,
            target_entity_id TEXT NOT NULL,
            relationship_type TEXT NOT NULL,
            evidence_chunks TEXT,
            confidence REAL,
            first_seen TEXT,
            last_seen TEXT,
            mention_count INTEGER DEFAULT 1,
            metadata TEXT,
            FOREIGN KEY (source_entity_id) REFERENCES entities(id),
            FOREIGN KEY (target_entity_id) REFERENCES entities(id),
            UNIQUE(source_entity_id, target_entity_id, relationship_type)
        )
    """)
    
    # Timeline events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS timeline_events (
            id TEXT PRIMARY KEY,
            event_date TEXT,
            event_date_precision TEXT,  -- day, month, year, approximate
            title TEXT NOT NULL,
            description TEXT,
            event_type TEXT,
            entities TEXT,
            evidence_chunks TEXT,
            source_documents TEXT,
            confidence REAL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            color TEXT,
            description TEXT
        )
    """)
    
    # Document tags junction table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_tags (
            document_id TEXT,
            tag_id TEXT,
            PRIMARY KEY (document_id, tag_id),
            FOREIGN KEY (document_id) REFERENCES documents(id),
            FOREIGN KEY (tag_id) REFERENCES tags(id)
        )
    """)
    
    # Processing queue table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_queue (
            id TEXT PRIMARY KEY,
            file_path TEXT NOT NULL,
            source_id TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 0,
            attempts INTEGER DEFAULT 0,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            started_at TEXT,
            completed_at TEXT
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_source ON documents(source_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(file_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_classification ON chunks(classification)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(normalized_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeline_date ON timeline_events(event_date)")
    
    # Full-text search
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            content,
            content='chunks',
            content_rowid='rowid'
        )
    """)
    
    conn.commit()
    
    # Insert default sources
    for source_id, source_data in SOURCES.items():
        cursor.execute("""
            INSERT OR IGNORE INTO sources (id, name, url, source_type, description)
            VALUES (?, ?, ?, ?, ?)
        """, (source_id, source_data["name"], source_data["url"], 
              source_data["type"], source_data["description"]))
    
    conn.commit()
    logger.info(f"Database initialized at {db_path}")
    return conn

# ============ FILE PROCESSING ============
class DocumentProcessor:
    """Handles document extraction, OCR, and text processing"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.conn = init_database(config["database_path"])
        
        # Create directories
        for dir_key in ["documents_dir", "processed_dir", "embeddings_dir"]:
            Path(config[dir_key]).mkdir(parents=True, exist_ok=True)
    
    def compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def extract_archive(self, archive_path: str, extract_to: str) -> List[str]:
        """Extract zip/tar archive and return list of extracted files"""
        extracted_files = []
        archive_path = Path(archive_path)
        extract_to = Path(extract_to)
        
        try:
            if archive_path.suffix.lower() == '.zip':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_to)
                    extracted_files = [str(extract_to / name) for name in zip_ref.namelist()]
            elif archive_path.suffix.lower() in ['.tar', '.gz', '.tgz']:
                with tarfile.open(archive_path, 'r:*') as tar_ref:
                    tar_ref.extractall(extract_to)
                    extracted_files = [str(extract_to / member.name) for member in tar_ref.getmembers()]
            
            logger.info(f"Extracted {len(extracted_files)} files from {archive_path}")
        except Exception as e:
            logger.error(f"Failed to extract {archive_path}: {e}")
        
        return extracted_files
    
    def get_file_type(self, file_path: str) -> str:
        """Determine file type from extension"""
        ext = Path(file_path).suffix.lower()
        type_map = {
            '.pdf': 'pdf',
            '.png': 'image', '.jpg': 'image', '.jpeg': 'image', 
            '.gif': 'image', '.tiff': 'image', '.bmp': 'image',
            '.txt': 'text', '.md': 'text', '.csv': 'text',
            '.doc': 'word', '.docx': 'word',
            '.xls': 'excel', '.xlsx': 'excel',
            '.eml': 'email', '.msg': 'email',
            '.html': 'html', '.htm': 'html',
            '.json': 'json', '.xml': 'xml'
        }
        return type_map.get(ext, 'unknown')
    
    def extract_text_from_pdf(self, file_path: str) -> Tuple[str, int]:
        """Extract text from PDF using multiple methods"""
        text = ""
        page_count = 0
        
        try:
            # Try PyPDF2 first (fast, works for text-based PDFs)
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text += page_text + "\n\n"
            
            # If we got very little text, try OCR
            if len(text.strip()) < 100 and page_count > 0:
                logger.info(f"PDF appears to be scanned, attempting OCR: {file_path}")
                text = self.ocr_pdf(file_path)
                
        except ImportError:
            logger.warning("PyPDF2 not installed, trying OCR directly")
            text = self.ocr_pdf(file_path)
        except Exception as e:
            logger.error(f"Error extracting PDF text from {file_path}: {e}")
            text = self.ocr_pdf(file_path)
        
        return text.strip(), page_count
    
    def ocr_pdf(self, file_path: str) -> str:
        """OCR a PDF file using pdf2image and pytesseract"""
        text = ""
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            images = convert_from_path(file_path, dpi=300)
            for i, image in enumerate(images):
                page_text = pytesseract.image_to_string(image)
                text += f"\n--- Page {i+1} ---\n{page_text}\n"
            
            logger.info(f"OCR completed for {file_path}: {len(images)} pages")
        except ImportError as e:
            logger.error(f"OCR dependencies not installed: {e}")
            logger.info("Install with: pip install pdf2image pytesseract")
        except Exception as e:
            logger.error(f"OCR failed for {file_path}: {e}")
        
        return text.strip()
    
    def ocr_image(self, file_path: str) -> str:
        """OCR an image file"""
        try:
            import pytesseract
            from PIL import Image
            
            image = Image.open(file_path)
            text = pytesseract.image_to_string(image)
            return text.strip()
        except ImportError:
            logger.error("pytesseract not installed")
            return ""
        except Exception as e:
            logger.error(f"OCR failed for image {file_path}: {e}")
            return ""
    
    def extract_text(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text from any supported file type"""
        file_type = self.get_file_type(file_path)
        text = ""
        metadata = {"file_type": file_type}
        
        if file_type == 'pdf':
            text, page_count = self.extract_text_from_pdf(file_path)
            metadata["page_count"] = page_count
            
        elif file_type == 'image':
            text = self.ocr_image(file_path)
            metadata["ocr"] = True
            
        elif file_type == 'text':
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
            except Exception as e:
                logger.error(f"Error reading text file {file_path}: {e}")
                
        elif file_type == 'word':
            try:
                import docx
                doc = docx.Document(file_path)
                text = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                logger.warning("python-docx not installed for Word file processing")
            except Exception as e:
                logger.error(f"Error reading Word file {file_path}: {e}")
                
        elif file_type == 'html':
            try:
                from bs4 import BeautifulSoup
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f.read(), 'html.parser')
                    text = soup.get_text(separator='\n')
            except ImportError:
                logger.warning("BeautifulSoup not installed for HTML processing")
            except Exception as e:
                logger.error(f"Error reading HTML file {file_path}: {e}")
                
        elif file_type == 'email':
            text, email_meta = self.parse_email(file_path)
            metadata.update(email_meta)
        
        return text.strip(), metadata
    
    def parse_email(self, file_path: str) -> Tuple[str, Dict]:
        """Parse email file and extract metadata"""
        import email
        from email import policy
        
        metadata = {}
        text = ""
        
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_binary_file(f, policy=policy.default)
            
            metadata["from"] = str(msg.get("From", ""))
            metadata["to"] = str(msg.get("To", ""))
            metadata["cc"] = str(msg.get("Cc", ""))
            metadata["subject"] = str(msg.get("Subject", ""))
            metadata["date"] = str(msg.get("Date", ""))
            
            # Extract body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        text += part.get_content() + "\n"
            else:
                text = msg.get_content()
            
            # Add header info to text
            header_text = f"From: {metadata['from']}\nTo: {metadata['to']}\n"
            header_text += f"Subject: {metadata['subject']}\nDate: {metadata['date']}\n\n"
            text = header_text + text
            
        except Exception as e:
            logger.error(f"Error parsing email {file_path}: {e}")
        
        return text.strip(), metadata
    
    def chunk_text(self, text: str, chunk_size: int = None, overlap: int = None) -> List[Dict]:
        """Split text into overlapping chunks"""
        if chunk_size is None:
            chunk_size = self.config["chunk_size"]
        if overlap is None:
            overlap = self.config["chunk_overlap"]
        
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for sep in ['. ', '.\n', '? ', '?\n', '! ', '!\n']:
                    last_sep = text[start:end].rfind(sep)
                    if last_sep > chunk_size * 0.5:  # At least halfway through
                        end = start + last_sep + len(sep)
                        break
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "chunk_index": chunk_index,
                    "content": chunk_text,
                    "start_char": start,
                    "end_char": end
                })
                chunk_index += 1
            
            start = end - overlap
        
        return chunks
    
    def process_file(self, file_path: str, source_id: str = "manual") -> Optional[str]:
        """Process a single file and add to database"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None
        
        # Check if already processed
        file_hash = self.compute_file_hash(str(file_path))
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM documents WHERE file_hash = ?", (file_hash,))
        existing = cursor.fetchone()
        
        if existing:
            logger.info(f"File already processed: {file_path}")
            return existing[0]
        
        # Extract text
        logger.info(f"Processing: {file_path}")
        text, metadata = self.extract_text(str(file_path))
        
        if not text:
            logger.warning(f"No text extracted from: {file_path}")
            return None
        
        # Create document record
        doc_id = hashlib.md5(f"{file_path}_{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        cursor.execute("""
            INSERT INTO documents (
                id, source_id, file_path, file_name, file_type,
                file_size, file_hash, created_at, processed_at, ocr_text,
                page_count, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id, source_id, str(file_path), file_path.name,
            self.get_file_type(str(file_path)), file_path.stat().st_size,
            file_hash, datetime.now().isoformat(), datetime.now().isoformat(),
            text, metadata.get("page_count", 1), json.dumps(metadata)
        ))
        
        # Create chunks
        chunks = self.chunk_text(text)
        for chunk in chunks:
            chunk_id = f"{doc_id}_{chunk['chunk_index']}"
            cursor.execute("""
                INSERT INTO chunks (
                    id, document_id, chunk_index, content, start_char, end_char
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk_id, doc_id, chunk['chunk_index'],
                chunk['content'], chunk['start_char'], chunk['end_char']
            ))
            
            # Add to FTS index
            cursor.execute("""
                INSERT INTO chunks_fts (rowid, content)
                SELECT rowid, content FROM chunks WHERE id = ?
            """, (chunk_id,))
        
        self.conn.commit()
        logger.info(f"Processed {file_path}: {len(chunks)} chunks created")
        
        return doc_id
    
    def process_directory(self, directory: str, source_id: str = "manual") -> Dict:
        """Process all files in a directory"""
        directory = Path(directory)
        results = {"processed": 0, "skipped": 0, "errors": 0, "documents": []}
        
        supported_extensions = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.tiff',
                               '.txt', '.md', '.doc', '.docx', '.html', '.htm',
                               '.eml', '.msg', '.csv', '.json'}
        
        files = [f for f in directory.rglob('*') 
                 if f.is_file() and f.suffix.lower() in supported_extensions]
        
        logger.info(f"Found {len(files)} files to process in {directory}")
        
        with ThreadPoolExecutor(max_workers=self.config["max_workers"]) as executor:
            future_to_file = {
                executor.submit(self.process_file, str(f), source_id): f 
                for f in files
            }
            
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    doc_id = future.result()
                    if doc_id:
                        results["processed"] += 1
                        results["documents"].append(doc_id)
                    else:
                        results["skipped"] += 1
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    results["errors"] += 1
        
        return results

# ============ AI CLASSIFICATION ============
class AIClassifier:
    """Uses Claude API to classify and analyze documents"""
    
    CLASSIFICATION_CATEGORIES = [
        "substantive_communication",  # Important emails, memos about power/politics
        "financial_records",          # Bank statements, transactions, invoices
        "travel_logistics",           # Flight manifests, schedules, itineraries
        "legal_documents",            # Contracts, court filings, legal correspondence
        "media_mentions",             # News clippings, press releases
        "personal_correspondence",    # Personal letters, birthday cards
        "contact_information",        # Address books, contact lists
        "meeting_notes",              # Meeting minutes, agendas
        "redacted_material",          # Heavily redacted documents
        "miscellaneous",              # Everything else
    ]
    
    def __init__(self, config: Dict):
        self.config = config
        self.api_key = config.get("anthropic_api_key", "")
        
    def classify_chunk(self, chunk_text: str) -> Dict:
        """Classify a text chunk using Claude API"""
        if not self.api_key:
            logger.warning("No Anthropic API key configured, using rule-based classification")
            return self.rule_based_classify(chunk_text)
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1024,
                    "messages": [{
                        "role": "user",
                        "content": f"""Analyze this document excerpt and provide:
1. Classification (one of: {', '.join(self.CLASSIFICATION_CATEGORIES)})
2. Relevance score (0-1, where 1 is highly relevant to investigating power networks, financial crimes, or political corruption)
3. Key entities mentioned (people, organizations, locations, dates, money amounts)
4. Brief summary (1-2 sentences)

Document excerpt:
{chunk_text[:3000]}

Respond in JSON format:
{{
    "classification": "category",
    "relevance_score": 0.0,
    "entities": [
        {{"name": "entity name", "type": "person|organization|location|date|money", "context": "brief context"}}
    ],
    "summary": "brief summary"
}}"""
                    }]
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["content"][0]["text"]
                # Parse JSON from response
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            else:
                logger.error(f"API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Classification error: {e}")
        
        return self.rule_based_classify(chunk_text)
    
    def rule_based_classify(self, text: str) -> Dict:
        """Fallback rule-based classification"""
        text_lower = text.lower()
        
        # Simple keyword-based classification
        if any(w in text_lower for w in ['$', 'payment', 'transfer', 'bank', 'account', 'wire']):
            classification = "financial_records"
            relevance = 0.7
        elif any(w in text_lower for w in ['flight', 'manifest', 'passenger', 'departure', 'arrival']):
            classification = "travel_logistics"
            relevance = 0.6
        elif any(w in text_lower for w in ['contract', 'agreement', 'court', 'legal', 'attorney']):
            classification = "legal_documents"
            relevance = 0.7
        elif any(w in text_lower for w in ['meeting', 'agenda', 'minutes', 'discussed']):
            classification = "meeting_notes"
            relevance = 0.5
        elif any(w in text_lower for w in ['dear', 'happy birthday', 'thank you for']):
            classification = "personal_correspondence"
            relevance = 0.2
        elif text.count('[REDACTED]') > 3 or text.count('████') > 3:
            classification = "redacted_material"
            relevance = 0.8
        else:
            classification = "miscellaneous"
            relevance = 0.3
        
        # Extract entities with regex
        entities = []
        
        # Names (simple pattern)
        names = re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', text)
        for name in set(names[:10]):
            entities.append({"name": name, "type": "person", "context": ""})
        
        # Money amounts
        money = re.findall(r'\$[\d,]+(?:\.\d{2})?|\d+(?:,\d{3})*(?:\.\d{2})?\s*(?:dollars|USD)', text)
        for amount in set(money[:5]):
            entities.append({"name": amount, "type": "money", "context": ""})
        
        # Dates
        dates = re.findall(r'\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b', text)
        for date in set(dates[:5]):
            entities.append({"name": date, "type": "date", "context": ""})
        
        return {
            "classification": classification,
            "relevance_score": relevance,
            "entities": entities,
            "summary": text[:200] + "..." if len(text) > 200 else text
        }
    
    def extract_entities(self, text: str) -> List[Dict]:
        """Extract named entities from text"""
        entities = []
        
        # Try spaCy if available
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm")
            doc = nlp(text[:100000])  # Limit text length
            
            for ent in doc.ents:
                entity_type_map = {
                    "PERSON": "person",
                    "ORG": "organization",
                    "GPE": "location",
                    "LOC": "location",
                    "DATE": "date",
                    "MONEY": "money",
                    "EVENT": "event"
                }
                if ent.label_ in entity_type_map:
                    entities.append({
                        "name": ent.text,
                        "type": entity_type_map[ent.label_],
                        "start": ent.start_char,
                        "end": ent.end_char
                    })
        except ImportError:
            logger.info("spaCy not installed, using regex-based entity extraction")
            # Fall back to regex
            result = self.rule_based_classify(text)
            entities = result.get("entities", [])
        
        return entities

# ============ ENTITY MANAGER ============
class EntityManager:
    """Manages entity extraction, deduplication, and relationship building"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def normalize_name(self, name: str) -> str:
        """Normalize entity name for deduplication"""
        # Remove extra whitespace, lowercase
        normalized = ' '.join(name.split()).lower()
        # Remove common titles
        for title in ['mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'hon.']:
            normalized = normalized.replace(title, '').strip()
        return normalized
    
    def add_or_update_entity(self, name: str, entity_type: str, 
                             chunk_id: str, document_id: str,
                             context: str = "", confidence: float = 1.0) -> str:
        """Add new entity or update existing one"""
        cursor = self.conn.cursor()
        normalized = self.normalize_name(name)
        
        # Check for existing entity
        cursor.execute("""
            SELECT id, mention_count, aliases FROM entities 
            WHERE normalized_name = ? AND entity_type = ?
        """, (normalized, entity_type))
        existing = cursor.fetchone()
        
        now = datetime.now().isoformat()
        
        if existing:
            entity_id = existing[0]
            mention_count = existing[1] + 1
            aliases = json.loads(existing[2] or '[]')
            
            # Add name variant if not already known
            if name not in aliases and name.lower() != normalized:
                aliases.append(name)
            
            cursor.execute("""
                UPDATE entities SET 
                    mention_count = ?,
                    last_seen = ?,
                    aliases = ?
                WHERE id = ?
            """, (mention_count, now, json.dumps(aliases), entity_id))
        else:
            entity_id = hashlib.md5(f"{normalized}_{entity_type}".encode()).hexdigest()[:16]
            cursor.execute("""
                INSERT INTO entities (
                    id, name, entity_type, normalized_name, aliases,
                    first_seen, last_seen, mention_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (entity_id, name, entity_type, normalized, '[]', now, now, 1))
        
        # Add mention record
        mention_id = hashlib.md5(f"{entity_id}_{chunk_id}_{now}".encode()).hexdigest()[:16]
        cursor.execute("""
            INSERT INTO entity_mentions (
                id, entity_id, chunk_id, document_id, context, confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (mention_id, entity_id, chunk_id, document_id, context, confidence))
        
        self.conn.commit()
        return entity_id
    
    def find_relationships(self, entity_id: str) -> List[Dict]:
        """Find all relationships for an entity"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT r.*, 
                   e1.name as source_name, e1.entity_type as source_type,
                   e2.name as target_name, e2.entity_type as target_type
            FROM relationships r
            JOIN entities e1 ON r.source_entity_id = e1.id
            JOIN entities e2 ON r.target_entity_id = e2.id
            WHERE r.source_entity_id = ? OR r.target_entity_id = ?
        """, (entity_id, entity_id))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def add_relationship(self, source_entity_id: str, target_entity_id: str,
                        relationship_type: str, evidence_chunk_id: str,
                        confidence: float = 0.8) -> str:
        """Add or update a relationship between entities"""
        cursor = self.conn.cursor()
        now = datetime.now().isoformat()
        
        # Check for existing relationship
        cursor.execute("""
            SELECT id, evidence_chunks, mention_count FROM relationships
            WHERE source_entity_id = ? AND target_entity_id = ? AND relationship_type = ?
        """, (source_entity_id, target_entity_id, relationship_type))
        existing = cursor.fetchone()
        
        if existing:
            rel_id = existing[0]
            evidence = json.loads(existing[1] or '[]')
            if evidence_chunk_id not in evidence:
                evidence.append(evidence_chunk_id)
            
            cursor.execute("""
                UPDATE relationships SET
                    evidence_chunks = ?,
                    mention_count = ?,
                    last_seen = ?,
                    confidence = MAX(confidence, ?)
                WHERE id = ?
            """, (json.dumps(evidence), existing[2] + 1, now, confidence, rel_id))
        else:
            rel_id = hashlib.md5(
                f"{source_entity_id}_{target_entity_id}_{relationship_type}".encode()
            ).hexdigest()[:16]
            
            cursor.execute("""
                INSERT INTO relationships (
                    id, source_entity_id, target_entity_id, relationship_type,
                    evidence_chunks, confidence, first_seen, last_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_entity_id, target_entity_id, relationship_type,
                  json.dumps([evidence_chunk_id]), confidence, now, now))
        
        self.conn.commit()
        return rel_id

# ============ SEARCH ENGINE ============
class SearchEngine:
    """Full-text and semantic search across the knowledge base"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
    
    def search_text(self, query: str, limit: int = 50) -> List[Dict]:
        """Full-text search across chunks"""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT c.id, c.document_id, c.content, c.classification,
                   c.relevance_score, d.file_name, d.source_id
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE c.id IN (
                SELECT rowid FROM chunks_fts WHERE chunks_fts MATCH ?
            )
            ORDER BY c.relevance_score DESC NULLS LAST
            LIMIT ?
        """, (query, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def search_entities(self, query: str, entity_type: str = None) -> List[Dict]:
        """Search for entities by name"""
        cursor = self.conn.cursor()
        
        query_normalized = f"%{query.lower()}%"
        
        if entity_type:
            cursor.execute("""
                SELECT * FROM entities
                WHERE (normalized_name LIKE ? OR aliases LIKE ?)
                AND entity_type = ?
                ORDER BY mention_count DESC
            """, (query_normalized, query_normalized, entity_type))
        else:
            cursor.execute("""
                SELECT * FROM entities
                WHERE normalized_name LIKE ? OR aliases LIKE ?
                ORDER BY mention_count DESC
            """, (query_normalized, query_normalized))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_entity_network(self, entity_id: str, depth: int = 2) -> Dict:
        """Get network of entities connected to a given entity"""
        cursor = self.conn.cursor()
        
        visited = set()
        nodes = []
        edges = []
        queue = [(entity_id, 0)]
        
        while queue:
            current_id, current_depth = queue.pop(0)
            
            if current_id in visited or current_depth > depth:
                continue
            
            visited.add(current_id)
            
            # Get entity info
            cursor.execute("SELECT * FROM entities WHERE id = ?", (current_id,))
            entity = cursor.fetchone()
            if entity:
                nodes.append(dict(entity))
            
            # Get relationships
            cursor.execute("""
                SELECT r.*, 
                       e1.name as source_name, e2.name as target_name
                FROM relationships r
                JOIN entities e1 ON r.source_entity_id = e1.id
                JOIN entities e2 ON r.target_entity_id = e2.id
                WHERE r.source_entity_id = ? OR r.target_entity_id = ?
            """, (current_id, current_id))
            
            for rel in cursor.fetchall():
                rel_dict = dict(rel)
                edges.append(rel_dict)
                
                # Add connected entities to queue
                other_id = rel_dict["target_entity_id"] if rel_dict["source_entity_id"] == current_id else rel_dict["source_entity_id"]
                if other_id not in visited:
                    queue.append((other_id, current_depth + 1))
        
        return {"nodes": nodes, "edges": edges}

# ============ API SERVER ============
def create_api_server(config: Dict):
    """Create Flask API server for the frontend"""
    try:
        from flask import Flask, jsonify, request
        from flask_cors import CORS
    except ImportError:
        logger.error("Flask not installed. Run: pip install flask flask-cors")
        return None
    
    app = Flask(__name__)
    CORS(app)
    
    processor = DocumentProcessor(config)
    classifier = AIClassifier(config)
    entity_manager = EntityManager(processor.conn)
    search_engine = SearchEngine(processor.conn)
    
    @app.route('/api/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok"})
    
    @app.route('/api/sources', methods=['GET'])
    def get_sources():
        cursor = processor.conn.cursor()
        cursor.execute("SELECT * FROM sources")
        return jsonify([dict(row) for row in cursor.fetchall()])
    
    @app.route('/api/documents', methods=['GET'])
    def get_documents():
        source_id = request.args.get('source_id')
        limit = int(request.args.get('limit', 100))
        offset = int(request.args.get('offset', 0))
        
        cursor = processor.conn.cursor()
        if source_id:
            cursor.execute("""
                SELECT * FROM documents WHERE source_id = ?
                ORDER BY processed_at DESC LIMIT ? OFFSET ?
            """, (source_id, limit, offset))
        else:
            cursor.execute("""
                SELECT * FROM documents
                ORDER BY processed_at DESC LIMIT ? OFFSET ?
            """, (limit, offset))
        
        return jsonify([dict(row) for row in cursor.fetchall()])
    
    @app.route('/api/documents/<doc_id>', methods=['GET'])
    def get_document(doc_id):
        cursor = processor.conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        doc = cursor.fetchone()
        if not doc:
            return jsonify({"error": "Not found"}), 404
        
        # Get chunks
        cursor.execute("SELECT * FROM chunks WHERE document_id = ? ORDER BY chunk_index", (doc_id,))
        chunks = [dict(row) for row in cursor.fetchall()]
        
        result = dict(doc)
        result["chunks"] = chunks
        return jsonify(result)
    
    @app.route('/api/search', methods=['GET'])
    def search():
        query = request.args.get('q', '')
        search_type = request.args.get('type', 'text')  # text, entities
        
        if search_type == 'entities':
            results = search_engine.search_entities(query)
        else:
            results = search_engine.search_text(query)
        
        return jsonify(results)
    
    @app.route('/api/entities', methods=['GET'])
    def get_entities():
        entity_type = request.args.get('type')
        limit = int(request.args.get('limit', 100))
        
        cursor = processor.conn.cursor()
        if entity_type:
            cursor.execute("""
                SELECT * FROM entities WHERE entity_type = ?
                ORDER BY mention_count DESC LIMIT ?
            """, (entity_type, limit))
        else:
            cursor.execute("""
                SELECT * FROM entities
                ORDER BY mention_count DESC LIMIT ?
            """, (limit,))
        
        return jsonify([dict(row) for row in cursor.fetchall()])
    
    @app.route('/api/entities/<entity_id>', methods=['GET'])
    def get_entity(entity_id):
        cursor = processor.conn.cursor()
        cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        entity = cursor.fetchone()
        if not entity:
            return jsonify({"error": "Not found"}), 404
        
        # Get relationships
        relationships = entity_manager.find_relationships(entity_id)
        
        # Get mentions
        cursor.execute("""
            SELECT em.*, c.content, d.file_name
            FROM entity_mentions em
            JOIN chunks c ON em.chunk_id = c.id
            JOIN documents d ON em.document_id = d.id
            WHERE em.entity_id = ?
            ORDER BY em.created_at DESC
            LIMIT 50
        """, (entity_id,))
        mentions = [dict(row) for row in cursor.fetchall()]
        
        result = dict(entity)
        result["relationships"] = relationships
        result["mentions"] = mentions
        return jsonify(result)
    
    @app.route('/api/entities/<entity_id>/network', methods=['GET'])
    def get_entity_network(entity_id):
        depth = int(request.args.get('depth', 2))
        network = search_engine.get_entity_network(entity_id, depth)
        return jsonify(network)
    
    @app.route('/api/relationships', methods=['GET'])
    def get_relationships():
        limit = int(request.args.get('limit', 100))
        cursor = processor.conn.cursor()
        cursor.execute("""
            SELECT r.*, 
                   e1.name as source_name, e1.entity_type as source_type,
                   e2.name as target_name, e2.entity_type as target_type
            FROM relationships r
            JOIN entities e1 ON r.source_entity_id = e1.id
            JOIN entities e2 ON r.target_entity_id = e2.id
            ORDER BY r.confidence DESC, r.mention_count DESC
            LIMIT ?
        """, (limit,))
        return jsonify([dict(row) for row in cursor.fetchall()])
    
    @app.route('/api/timeline', methods=['GET'])
    def get_timeline():
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        cursor = processor.conn.cursor()
        if start_date and end_date:
            cursor.execute("""
                SELECT * FROM timeline_events
                WHERE event_date >= ? AND event_date <= ?
                ORDER BY event_date
            """, (start_date, end_date))
        else:
            cursor.execute("SELECT * FROM timeline_events ORDER BY event_date")
        
        return jsonify([dict(row) for row in cursor.fetchall()])
    
    @app.route('/api/process', methods=['POST'])
    def process_files():
        data = request.json
        file_path = data.get('file_path')
        source_id = data.get('source_id', 'manual')
        
        if not file_path:
            return jsonify({"error": "file_path required"}), 400
        
        path = Path(file_path)
        if path.is_dir():
            results = processor.process_directory(str(path), source_id)
        else:
            doc_id = processor.process_file(str(path), source_id)
            results = {"processed": 1 if doc_id else 0, "documents": [doc_id] if doc_id else []}
        
        return jsonify(results)
    
    @app.route('/api/classify', methods=['POST'])
    def classify_chunk():
        data = request.json
        chunk_id = data.get('chunk_id')
        
        cursor = processor.conn.cursor()
        cursor.execute("SELECT content FROM chunks WHERE id = ?", (chunk_id,))
        chunk = cursor.fetchone()
        
        if not chunk:
            return jsonify({"error": "Chunk not found"}), 404
        
        result = classifier.classify_chunk(chunk[0])
        
        # Update chunk with classification
        cursor.execute("""
            UPDATE chunks SET 
                classification = ?,
                relevance_score = ?,
                entities = ?
            WHERE id = ?
        """, (result["classification"], result["relevance_score"],
              json.dumps(result.get("entities", [])), chunk_id))
        processor.conn.commit()
        
        return jsonify(result)
    
    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        cursor = processor.conn.cursor()
        
        stats = {}
        cursor.execute("SELECT COUNT(*) FROM documents")
        stats["total_documents"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        stats["total_chunks"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM entities")
        stats["total_entities"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM relationships")
        stats["total_relationships"] = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT entity_type, COUNT(*) as count 
            FROM entities GROUP BY entity_type
        """)
        stats["entities_by_type"] = {row[0]: row[1] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT classification, COUNT(*) as count 
            FROM chunks WHERE classification IS NOT NULL
            GROUP BY classification
        """)
        stats["chunks_by_classification"] = {row[0]: row[1] for row in cursor.fetchall()}
        
        return jsonify(stats)
    
    return app

# ============ CLI ============
def main():
    """Command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SHADOW Investigation Platform")
    subparsers = parser.add_subparsers(dest='command')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize database')
    
    # Process command
    process_parser = subparsers.add_parser('process', help='Process documents')
    process_parser.add_argument('path', help='File or directory path')
    process_parser.add_argument('--source', default='manual', help='Source ID')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search documents')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--type', choices=['text', 'entities'], default='text')
    
    # Server command
    server_parser = subparsers.add_parser('server', help='Start API server')
    server_parser.add_argument('--port', type=int, default=5000)
    server_parser.add_argument('--host', default='127.0.0.1')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')
    
    args = parser.parse_args()
    
    if args.command == 'init':
        init_database(CONFIG["database_path"])
        print("Database initialized successfully")
        
    elif args.command == 'process':
        processor = DocumentProcessor(CONFIG)
        path = Path(args.path)
        
        if path.is_dir():
            results = processor.process_directory(str(path), args.source)
            print(f"Processed: {results['processed']}, Skipped: {results['skipped']}, Errors: {results['errors']}")
        else:
            doc_id = processor.process_file(str(path), args.source)
            if doc_id:
                print(f"Document processed: {doc_id}")
            else:
                print("Processing failed")
                
    elif args.command == 'search':
        conn = init_database(CONFIG["database_path"])
        search_engine = SearchEngine(conn)
        
        if args.type == 'entities':
            results = search_engine.search_entities(args.query)
        else:
            results = search_engine.search_text(args.query)
        
        for i, result in enumerate(results[:20]):
            print(f"\n--- Result {i+1} ---")
            if args.type == 'entities':
                print(f"Name: {result['name']}")
                print(f"Type: {result['entity_type']}")
                print(f"Mentions: {result['mention_count']}")
            else:
                print(f"File: {result.get('file_name', 'Unknown')}")
                print(f"Classification: {result.get('classification', 'Unknown')}")
                print(f"Content: {result['content'][:200]}...")
                
    elif args.command == 'server':
        app = create_api_server(CONFIG)
        if app:
            print(f"Starting server on {args.host}:{args.port}")
            app.run(host=args.host, port=args.port, debug=True)
        else:
            print("Failed to create server. Install Flask: pip install flask flask-cors")
            
    elif args.command == 'stats':
        conn = init_database(CONFIG["database_path"])
        cursor = conn.cursor()
        
        print("\n=== SHADOW Knowledge Base Statistics ===\n")
        
        cursor.execute("SELECT COUNT(*) FROM documents")
        print(f"Total Documents: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM chunks")
        print(f"Total Chunks: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM entities")
        print(f"Total Entities: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM relationships")
        print(f"Total Relationships: {cursor.fetchone()[0]}")
        
        print("\nEntities by Type:")
        cursor.execute("SELECT entity_type, COUNT(*) FROM entities GROUP BY entity_type")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
        print("\nTop 10 Most Mentioned Entities:")
        cursor.execute("SELECT name, entity_type, mention_count FROM entities ORDER BY mention_count DESC LIMIT 10")
        for row in cursor.fetchall():
            print(f"  {row[0]} ({row[1]}): {row[2]} mentions")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
