#!/usr/bin/env python3
"""
SHADOW Vector Database Integration
Semantic search and AI-powered document/entity linking using embeddings
Supports: ChromaDB (local), Qdrant, Weaviate, LanceDB
"""

import os
import json
import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
import logging
import numpy as np

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ CONFIGURATION ============
CONFIG = {
    "vector_db": "chroma",  # chroma, qdrant, weaviate, lancedb
    "chroma_persist_dir": "./chroma_db",
    "embedding_model": "all-MiniLM-L6-v2",  # sentence-transformers model
    "embedding_dim": 384,
    "chunk_size": 1000,
    "chunk_overlap": 100,
    "batch_size": 100,
    "anthropic_api_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
}

# ============ EMBEDDING SERVICE ============
class EmbeddingService:
    """Generate embeddings using various providers"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.model = None
        self.provider = None
        
    def init_local_model(self):
        """Initialize local sentence-transformers model"""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.config["embedding_model"])
            self.provider = "local"
            logger.info(f"Loaded local embedding model: {self.config['embedding_model']}")
        except ImportError:
            logger.warning("sentence-transformers not installed, falling back to API")
            self.init_api_model()
    
    def init_api_model(self):
        """Initialize OpenAI embedding API"""
        if self.config.get("openai_api_key"):
            self.provider = "openai"
            logger.info("Using OpenAI embeddings API")
        else:
            logger.error("No embedding provider available!")
            self.provider = None
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts"""
        if self.model is None and self.provider is None:
            self.init_local_model()
        
        if self.provider == "local":
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        
        elif self.provider == "openai":
            import openai
            openai.api_key = self.config["openai_api_key"]
            
            embeddings = []
            for text in texts:
                response = openai.Embedding.create(
                    model="text-embedding-ada-002",
                    input=text[:8000]  # Truncate for API limits
                )
                embeddings.append(response["data"][0]["embedding"])
            return embeddings
        
        else:
            # Return zero vectors as fallback
            return [[0.0] * self.config["embedding_dim"] for _ in texts]
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        return self.embed_texts([text])[0]


# ============ CHROMA DB INTEGRATION ============
class ChromaVectorDB:
    """ChromaDB vector database integration"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.client = None
        self.collections = {}
        self.embedding_service = EmbeddingService(config)
    
    def init(self):
        """Initialize ChromaDB client"""
        try:
            import chromadb
            from chromadb.config import Settings
            
            persist_dir = Path(self.config["chroma_persist_dir"])
            persist_dir.mkdir(parents=True, exist_ok=True)
            
            self.client = chromadb.Client(Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(persist_dir),
                anonymized_telemetry=False
            ))
            
            logger.info(f"ChromaDB initialized at {persist_dir}")
        except ImportError:
            logger.error("chromadb not installed. Run: pip install chromadb")
            raise
    
    def get_or_create_collection(self, name: str):
        """Get or create a collection"""
        if self.client is None:
            self.init()
        
        if name not in self.collections:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        
        return self.collections[name]
    
    def add_documents(self, collection_name: str, documents: List[Dict]):
        """Add documents to a collection"""
        collection = self.get_or_create_collection(collection_name)
        
        ids = []
        texts = []
        metadatas = []
        
        for doc in documents:
            doc_id = doc.get("id") or hashlib.md5(doc["text"].encode()).hexdigest()[:16]
            ids.append(doc_id)
            texts.append(doc["text"])
            metadatas.append({
                k: v for k, v in doc.items() 
                if k not in ["id", "text", "embedding"] and v is not None
            })
        
        # Generate embeddings
        embeddings = self.embedding_service.embed_texts(texts)
        
        # Add to collection
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas
        )
        
        logger.info(f"Added {len(documents)} documents to {collection_name}")
    
    def search(self, collection_name: str, query: str, n_results: int = 10, 
               where: Dict = None) -> List[Dict]:
        """Semantic search in a collection"""
        collection = self.get_or_create_collection(collection_name)
        
        query_embedding = self.embedding_service.embed_text(query)
        
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where
        )
        
        documents = []
        for i, doc_id in enumerate(results["ids"][0]):
            documents.append({
                "id": doc_id,
                "text": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
                "score": 1 - results["distances"][0][i] if results["distances"] else 1
            })
        
        return documents
    
    def find_similar(self, collection_name: str, document_id: str, 
                     n_results: int = 10) -> List[Dict]:
        """Find documents similar to a given document"""
        collection = self.get_or_create_collection(collection_name)
        
        # Get the document's embedding
        result = collection.get(ids=[document_id], include=["embeddings"])
        
        if not result["embeddings"]:
            return []
        
        embedding = result["embeddings"][0]
        
        # Search for similar
        results = collection.query(
            query_embeddings=[embedding],
            n_results=n_results + 1  # Include self
        )
        
        documents = []
        for i, doc_id in enumerate(results["ids"][0]):
            if doc_id != document_id:  # Exclude the query document
                documents.append({
                    "id": doc_id,
                    "text": results["documents"][0][i] if results["documents"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                    "score": 1 - results["distances"][0][i] if results["distances"] else 1
                })
        
        return documents[:n_results]
    
    def persist(self):
        """Persist the database"""
        if self.client:
            self.client.persist()


# ============ AI LINKER ============
class AILinker:
    """
    AI-powered document and entity linking
    Uses embeddings for similarity + LLM for relationship extraction
    """
    
    def __init__(self, vector_db: ChromaVectorDB, knowledge_db: sqlite3.Connection, config: Dict):
        self.vector_db = vector_db
        self.knowledge_db = knowledge_db
        self.config = config
    
    def ingest_chunks(self, chunks: List[Dict], collection: str = "chunks"):
        """Ingest text chunks into vector database"""
        batch = []
        
        for chunk in chunks:
            batch.append({
                "id": chunk["id"],
                "text": chunk["content"],
                "document_id": chunk.get("document_id"),
                "chunk_index": chunk.get("chunk_index"),
                "classification": chunk.get("classification"),
                "source_id": chunk.get("source_id")
            })
            
            if len(batch) >= self.config["batch_size"]:
                self.vector_db.add_documents(collection, batch)
                batch = []
        
        if batch:
            self.vector_db.add_documents(collection, batch)
    
    def ingest_entities(self, entities: List[Dict], collection: str = "entities"):
        """Ingest entities into vector database"""
        documents = []
        
        for entity in entities:
            # Create a rich text representation of the entity
            text = f"{entity['name']} ({entity['entity_type']})"
            if entity.get("aliases"):
                text += f" Also known as: {', '.join(entity['aliases'])}"
            if entity.get("description"):
                text += f" {entity['description']}"
            
            documents.append({
                "id": entity["id"],
                "text": text,
                "name": entity["name"],
                "entity_type": entity["entity_type"],
                "mention_count": entity.get("mention_count", 0)
            })
        
        self.vector_db.add_documents(collection, documents)
    
    def find_related_chunks(self, query: str, n_results: int = 20, 
                           filters: Dict = None) -> List[Dict]:
        """Find chunks related to a query"""
        return self.vector_db.search("chunks", query, n_results, filters)
    
    def find_related_entities(self, entity_name: str, n_results: int = 10) -> List[Dict]:
        """Find entities related to a given entity"""
        # First, search by semantic similarity
        similar = self.vector_db.search("entities", entity_name, n_results)
        
        # Also check for co-occurrence in documents
        cursor = self.knowledge_db.cursor()
        cursor.execute("""
            SELECT DISTINCT e2.id, e2.name, e2.entity_type, e2.mention_count,
                   COUNT(*) as co_occurrence
            FROM entity_mentions em1
            JOIN entity_mentions em2 ON em1.chunk_id = em2.chunk_id
            JOIN entities e1 ON em1.entity_id = e1.id
            JOIN entities e2 ON em2.entity_id = e2.id
            WHERE e1.name LIKE ? AND e1.id != e2.id
            GROUP BY e2.id
            ORDER BY co_occurrence DESC
            LIMIT ?
        """, (f"%{entity_name}%", n_results))
        
        co_occurring = [dict(row) for row in cursor.fetchall()]
        
        # Merge and rank results
        results = {}
        for item in similar:
            entity_id = item["id"]
            results[entity_id] = {
                **item,
                "semantic_score": item["score"],
                "co_occurrence": 0
            }
        
        for item in co_occurring:
            entity_id = item["id"]
            if entity_id in results:
                results[entity_id]["co_occurrence"] = item["co_occurrence"]
            else:
                results[entity_id] = {
                    "id": entity_id,
                    "name": item["name"],
                    "entity_type": item["entity_type"],
                    "semantic_score": 0,
                    "co_occurrence": item["co_occurrence"]
                }
        
        # Calculate combined score
        for entity_id in results:
            r = results[entity_id]
            r["combined_score"] = (r.get("semantic_score", 0) * 0.6 + 
                                   min(r.get("co_occurrence", 0) / 10, 1) * 0.4)
        
        return sorted(results.values(), key=lambda x: x["combined_score"], reverse=True)[:n_results]
    
    def suggest_connections(self, entity_id: str, threshold: float = 0.7) -> List[Dict]:
        """Suggest potential connections for an entity"""
        cursor = self.knowledge_db.cursor()
        
        # Get entity info
        cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        entity = dict(cursor.fetchone())
        
        # Find semantically similar entities
        similar = self.vector_db.search("entities", entity["name"], 20)
        
        suggestions = []
        for item in similar:
            if item["id"] != entity_id and item["score"] >= threshold:
                # Check if relationship already exists
                cursor.execute("""
                    SELECT * FROM relationships
                    WHERE (source_entity_id = ? AND target_entity_id = ?)
                       OR (source_entity_id = ? AND target_entity_id = ?)
                """, (entity_id, item["id"], item["id"], entity_id))
                
                if not cursor.fetchone():
                    suggestions.append({
                        "entity_id": item["id"],
                        "entity_name": item["metadata"].get("name", "Unknown"),
                        "entity_type": item["metadata"].get("entity_type", "unknown"),
                        "confidence": item["score"],
                        "reason": "semantic_similarity"
                    })
        
        return suggestions
    
    def find_cross_document_links(self, document_id: str, n_results: int = 10) -> List[Dict]:
        """Find links between a document and other documents"""
        cursor = self.knowledge_db.cursor()
        
        # Get chunks from this document
        cursor.execute("SELECT id, content FROM chunks WHERE document_id = ?", (document_id,))
        chunks = [dict(row) for row in cursor.fetchall()]
        
        if not chunks:
            return []
        
        # Combine chunk text for query
        combined_text = " ".join([c["content"][:500] for c in chunks[:5]])
        
        # Find similar chunks from other documents
        similar = self.vector_db.search(
            "chunks", 
            combined_text, 
            n_results * 3,
            where={"document_id": {"$ne": document_id}}
        )
        
        # Group by document
        doc_scores = {}
        for item in similar:
            doc_id = item["metadata"].get("document_id")
            if doc_id and doc_id != document_id:
                if doc_id not in doc_scores:
                    doc_scores[doc_id] = {"score": 0, "matches": []}
                doc_scores[doc_id]["score"] += item["score"]
                doc_scores[doc_id]["matches"].append(item)
        
        # Get document info and sort
        results = []
        for doc_id, data in sorted(doc_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:n_results]:
            cursor.execute("SELECT file_name, classification FROM documents WHERE id = ?", (doc_id,))
            doc_info = cursor.fetchone()
            if doc_info:
                results.append({
                    "document_id": doc_id,
                    "file_name": doc_info["file_name"],
                    "classification": doc_info["classification"],
                    "relevance_score": data["score"] / len(data["matches"]),
                    "matching_chunks": len(data["matches"])
                })
        
        return results
    
    def extract_relationships_with_llm(self, text: str) -> List[Dict]:
        """Use LLM to extract relationships from text"""
        if not self.config.get("anthropic_api_key"):
            return []
        
        import requests
        
        prompt = f"""Analyze this text and extract any relationships between entities (people, organizations, locations).

Text:
{text[:4000]}

Return a JSON array of relationships in this format:
[
    {{
        "source": "Entity Name 1",
        "source_type": "person|organization|location",
        "target": "Entity Name 2", 
        "target_type": "person|organization|location",
        "relationship": "type of relationship (e.g., 'works for', 'located in', 'met with', 'paid', 'associated with')",
        "evidence": "brief quote or context from text",
        "confidence": 0.0-1.0
    }}
]

Only include relationships explicitly stated or strongly implied in the text.
"""
        
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config["anthropic_api_key"],
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2048,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            
            if response.status_code == 200:
                content = response.json()["content"][0]["text"]
                # Parse JSON from response
                import re
                json_match = re.search(r'\[.*\]', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            logger.error(f"LLM relationship extraction error: {e}")
        
        return []
    
    def build_knowledge_graph(self, source_id: str = None):
        """Build/update knowledge graph from processed documents"""
        cursor = self.knowledge_db.cursor()
        
        # Get unprocessed chunks
        if source_id:
            cursor.execute("""
                SELECT c.* FROM chunks c
                JOIN documents d ON c.document_id = d.id
                WHERE d.source_id = ? AND c.entities IS NULL
                LIMIT 1000
            """, (source_id,))
        else:
            cursor.execute("""
                SELECT * FROM chunks WHERE entities IS NULL LIMIT 1000
            """)
        
        chunks = [dict(row) for row in cursor.fetchall()]
        logger.info(f"Processing {len(chunks)} chunks for knowledge graph")
        
        for chunk in chunks:
            # Extract relationships using LLM
            relationships = self.extract_relationships_with_llm(chunk["content"])
            
            # Store extracted relationships
            for rel in relationships:
                # Add/update entities
                source_entity_id = self._add_entity(
                    rel["source"], 
                    rel["source_type"],
                    chunk["id"],
                    chunk["document_id"]
                )
                target_entity_id = self._add_entity(
                    rel["target"],
                    rel["target_type"],
                    chunk["id"],
                    chunk["document_id"]
                )
                
                # Add relationship
                self._add_relationship(
                    source_entity_id,
                    target_entity_id,
                    rel["relationship"],
                    chunk["id"],
                    rel["confidence"]
                )
            
            # Mark chunk as processed
            cursor.execute(
                "UPDATE chunks SET entities = ? WHERE id = ?",
                (json.dumps(relationships), chunk["id"])
            )
            self.knowledge_db.commit()
    
    def _add_entity(self, name: str, entity_type: str, chunk_id: str, document_id: str) -> str:
        """Add or update an entity"""
        cursor = self.knowledge_db.cursor()
        normalized = name.lower().strip()
        
        # Check for existing
        cursor.execute("""
            SELECT id FROM entities 
            WHERE normalized_name = ? AND entity_type = ?
        """, (normalized, entity_type))
        existing = cursor.fetchone()
        
        if existing:
            entity_id = existing[0]
            cursor.execute("""
                UPDATE entities SET mention_count = mention_count + 1
                WHERE id = ?
            """, (entity_id,))
        else:
            entity_id = hashlib.md5(f"{normalized}_{entity_type}".encode()).hexdigest()[:16]
            cursor.execute("""
                INSERT INTO entities (id, name, entity_type, normalized_name, mention_count)
                VALUES (?, ?, ?, ?, 1)
            """, (entity_id, name, entity_type, normalized))
        
        # Add mention
        mention_id = hashlib.md5(f"{entity_id}_{chunk_id}".encode()).hexdigest()[:16]
        cursor.execute("""
            INSERT OR IGNORE INTO entity_mentions (id, entity_id, chunk_id, document_id)
            VALUES (?, ?, ?, ?)
        """, (mention_id, entity_id, chunk_id, document_id))
        
        self.knowledge_db.commit()
        return entity_id
    
    def _add_relationship(self, source_id: str, target_id: str, rel_type: str, 
                          chunk_id: str, confidence: float):
        """Add or update a relationship"""
        cursor = self.knowledge_db.cursor()
        
        cursor.execute("""
            SELECT id, evidence_chunks, mention_count FROM relationships
            WHERE source_entity_id = ? AND target_entity_id = ? AND relationship_type = ?
        """, (source_id, target_id, rel_type))
        existing = cursor.fetchone()
        
        if existing:
            evidence = json.loads(existing[1] or "[]")
            if chunk_id not in evidence:
                evidence.append(chunk_id)
            cursor.execute("""
                UPDATE relationships SET
                    evidence_chunks = ?,
                    mention_count = ?,
                    confidence = MAX(confidence, ?)
                WHERE id = ?
            """, (json.dumps(evidence), existing[2] + 1, confidence, existing[0]))
        else:
            rel_id = hashlib.md5(f"{source_id}_{target_id}_{rel_type}".encode()).hexdigest()[:16]
            cursor.execute("""
                INSERT INTO relationships (
                    id, source_entity_id, target_entity_id, relationship_type,
                    evidence_chunks, confidence, first_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (rel_id, source_id, target_id, rel_type, 
                  json.dumps([chunk_id]), confidence, datetime.now().isoformat()))
        
        self.knowledge_db.commit()


# ============ PATTERN DETECTOR ============
class PatternDetector:
    """Detect patterns and anomalies in the knowledge base"""
    
    def __init__(self, vector_db: ChromaVectorDB, knowledge_db: sqlite3.Connection):
        self.vector_db = vector_db
        self.knowledge_db = knowledge_db
    
    def find_clusters(self, collection: str = "entities", n_clusters: int = 10) -> List[Dict]:
        """Find clusters of related entities"""
        # This would use more sophisticated clustering in production
        # For now, group by co-occurrence
        cursor = self.knowledge_db.cursor()
        
        cursor.execute("""
            SELECT e.entity_type, COUNT(*) as count,
                   GROUP_CONCAT(DISTINCT e.name) as entities
            FROM entities e
            GROUP BY e.entity_type
            ORDER BY count DESC
        """)
        
        clusters = []
        for row in cursor.fetchall():
            entities = row[2].split(",") if row[2] else []
            clusters.append({
                "type": row[0],
                "count": row[1],
                "sample_entities": entities[:10]
            })
        
        return clusters
    
    def find_anomalies(self) -> List[Dict]:
        """Find anomalous patterns in the data"""
        anomalies = []
        cursor = self.knowledge_db.cursor()
        
        # 1. Unusually high connection counts
        cursor.execute("""
            SELECT e.id, e.name, e.entity_type, COUNT(*) as connection_count
            FROM entities e
            JOIN relationships r ON e.id = r.source_entity_id OR e.id = r.target_entity_id
            GROUP BY e.id
            HAVING connection_count > (
                SELECT AVG(cnt) + 2 * 
                       (SELECT AVG((cnt - avg_cnt) * (cnt - avg_cnt)) 
                        FROM (SELECT COUNT(*) as cnt FROM relationships GROUP BY source_entity_id))
                FROM (SELECT COUNT(*) as cnt FROM relationships GROUP BY source_entity_id),
                     (SELECT AVG(cnt) as avg_cnt FROM (SELECT COUNT(*) as cnt FROM relationships GROUP BY source_entity_id))
            )
            ORDER BY connection_count DESC
            LIMIT 20
        """)
        
        for row in cursor.fetchall():
            anomalies.append({
                "type": "high_connectivity",
                "entity": row[1],
                "entity_type": row[2],
                "connection_count": row[3],
                "description": f"Unusually high number of connections ({row[3]})"
            })
        
        # 2. Cross-source connections (entities appearing in multiple FOIA sources)
        cursor.execute("""
            SELECT e.name, e.entity_type, COUNT(DISTINCT d.source_id) as source_count,
                   GROUP_CONCAT(DISTINCT d.source_id) as sources
            FROM entities e
            JOIN entity_mentions em ON e.id = em.entity_id
            JOIN documents d ON em.document_id = d.id
            GROUP BY e.id
            HAVING source_count > 2
            ORDER BY source_count DESC
            LIMIT 20
        """)
        
        for row in cursor.fetchall():
            anomalies.append({
                "type": "cross_source",
                "entity": row[0],
                "entity_type": row[1],
                "source_count": row[2],
                "sources": row[3].split(",") if row[3] else [],
                "description": f"Appears across {row[2]} different FOIA sources"
            })
        
        # 3. Redaction patterns (documents with high redaction indicators)
        cursor.execute("""
            SELECT d.id, d.file_name, d.source_id,
                   (LENGTH(d.ocr_text) - LENGTH(REPLACE(LOWER(d.ocr_text), 'redacted', ''))) / 8 as redaction_count
            FROM documents d
            WHERE d.ocr_text IS NOT NULL
            HAVING redaction_count > 10
            ORDER BY redaction_count DESC
            LIMIT 20
        """)
        
        for row in cursor.fetchall():
            anomalies.append({
                "type": "high_redaction",
                "document": row[1],
                "source": row[2],
                "redaction_count": row[3],
                "description": f"Contains {row[3]} redaction markers"
            })
        
        return anomalies
    
    def find_timeline_clusters(self) -> List[Dict]:
        """Find clusters of events around specific dates"""
        cursor = self.knowledge_db.cursor()
        
        cursor.execute("""
            SELECT date_released, COUNT(*) as doc_count,
                   GROUP_CONCAT(DISTINCT source_id) as sources
            FROM documents
            WHERE date_released IS NOT NULL
            GROUP BY substr(date_released, 1, 7)  -- Group by month
            HAVING doc_count > 50
            ORDER BY date_released
        """)
        
        clusters = []
        for row in cursor.fetchall():
            clusters.append({
                "period": row[0][:7],
                "document_count": row[1],
                "sources": row[2].split(",") if row[2] else []
            })
        
        return clusters


# ============ CLI ============
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="SHADOW Vector Database")
    subparsers = parser.add_subparsers(dest='command')
    
    # Ingest command
    ingest_parser = subparsers.add_parser('ingest', help='Ingest documents into vector DB')
    ingest_parser.add_argument('--source', help='Source ID to ingest')
    ingest_parser.add_argument('--type', choices=['chunks', 'entities'], default='chunks')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Semantic search')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--collection', default='chunks')
    search_parser.add_argument('--limit', type=int, default=10)
    
    # Link command
    link_parser = subparsers.add_parser('link', help='Find links and relationships')
    link_parser.add_argument('--entity', help='Entity name to find links for')
    link_parser.add_argument('--document', help='Document ID to find cross-references for')
    
    # Patterns command
    patterns_parser = subparsers.add_parser('patterns', help='Detect patterns and anomalies')
    
    # Build graph command
    build_parser = subparsers.add_parser('build-graph', help='Build knowledge graph with LLM')
    build_parser.add_argument('--source', help='Source ID to process')
    
    args = parser.parse_args()
    
    # Initialize
    from shadow_backend import init_database
    knowledge_db = init_database("shadow_knowledge.db")
    vector_db = ChromaVectorDB(CONFIG)
    linker = AILinker(vector_db, knowledge_db, CONFIG)
    
    if args.command == 'ingest':
        cursor = knowledge_db.cursor()
        
        if args.type == 'chunks':
            if args.source:
                cursor.execute("""
                    SELECT c.* FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    WHERE d.source_id = ?
                """, (args.source,))
            else:
                cursor.execute("SELECT * FROM chunks")
            
            chunks = [dict(row) for row in cursor.fetchall()]
            linker.ingest_chunks(chunks)
            print(f"Ingested {len(chunks)} chunks")
            
        elif args.type == 'entities':
            cursor.execute("SELECT * FROM entities")
            entities = [dict(row) for row in cursor.fetchall()]
            linker.ingest_entities(entities)
            print(f"Ingested {len(entities)} entities")
    
    elif args.command == 'search':
        results = linker.find_related_chunks(args.query, args.limit)
        print(f"\n=== Search Results for '{args.query}' ===\n")
        for i, result in enumerate(results):
            print(f"{i+1}. [{result['score']:.2f}] {result['text'][:200]}...")
            print(f"   Document: {result['metadata'].get('document_id', 'Unknown')}")
            print()
    
    elif args.command == 'link':
        if args.entity:
            results = linker.find_related_entities(args.entity)
            print(f"\n=== Entities Related to '{args.entity}' ===\n")
            for r in results:
                print(f"- {r['name']} ({r.get('entity_type', 'unknown')})")
                print(f"  Combined Score: {r.get('combined_score', 0):.2f}")
                print()
        
        elif args.document:
            results = linker.find_cross_document_links(args.document)
            print(f"\n=== Documents Related to '{args.document}' ===\n")
            for r in results:
                print(f"- {r['file_name']}")
                print(f"  Relevance: {r['relevance_score']:.2f}, Matches: {r['matching_chunks']}")
                print()
    
    elif args.command == 'patterns':
        detector = PatternDetector(vector_db, knowledge_db)
        
        print("\n=== Anomalies Detected ===\n")
        anomalies = detector.find_anomalies()
        for a in anomalies[:20]:
            print(f"[{a['type']}] {a.get('entity') or a.get('document')}")
            print(f"  {a['description']}")
            print()
        
        print("\n=== Timeline Clusters ===\n")
        clusters = detector.find_timeline_clusters()
        for c in clusters[:10]:
            print(f"{c['period']}: {c['document_count']} documents")
    
    elif args.command == 'build-graph':
        linker.build_knowledge_graph(args.source)
        print("Knowledge graph updated")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
