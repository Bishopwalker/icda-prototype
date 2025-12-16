"""
Knowledge Document Indexing for ICDA RAG
========================================

Supports two modes:
1. OpenSearch mode - Full vector search (when OpenSearch available)
2. Memory mode - Simple keyword search fallback (no dependencies)

Usage:
    knowledge = KnowledgeManager(embedder, opensearch_client)
    # OR for lite mode:
    knowledge = KnowledgeManager(embedder, None)  # Uses in-memory fallback
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .embeddings import EmbeddingClient


class DocumentProcessor:
    """Extract and chunk content from various file formats."""

    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50

    def process_file(self, path: Path) -> list[dict]:
        """Process a file into chunks."""
        suffix = path.suffix.lower()

        try:
            # Plain text formats
            if suffix in (".txt", ".md", ".markdown", ".log", ".cfg", ".ini", ".env",
                          ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".yaml", ".yml",
                          ".xml", ".rtf"):
                content = path.read_text(encoding="utf-8", errors="ignore")
            elif suffix == ".json":
                data = json.loads(path.read_text(encoding="utf-8"))
                content = self._json_to_text(data)
            elif suffix == ".csv":
                content = self._read_csv(path)
            elif suffix in (".html", ".htm"):
                content = self._read_html(path)
            elif suffix == ".pdf":
                content = self._read_pdf(path)
            elif suffix == ".docx":
                content = self._read_docx(path)
            elif suffix == ".doc":
                content = self._read_doc(path)
            elif suffix in (".odt", ".odf"):
                content = self._read_odf(path)
            elif suffix in (".xlsx", ".xls"):
                content = self._read_excel(path)
            else:
                # Try to read as text for any unknown format
                content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"Error reading {path}: {e}")
            return []

        if not content:
            return []

        return self.chunk_text(content, path.name)

    def process_text(self, content: str, source_name: str = "direct") -> list[dict]:
        """Process raw text content into chunks."""
        return self.chunk_text(content, source_name)

    def chunk_text(self, content: str, source_name: str) -> list[dict]:
        """Split content into overlapping chunks at paragraph boundaries."""
        content = self._clean_text(content)
        if not content:
            return []

        paragraphs = re.split(r'\n\s*\n', content)
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para.split())

            if para_size > self.CHUNK_SIZE:
                if current_chunk:
                    chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                    current_chunk = []
                    current_size = 0

                sentences = re.split(r'(?<=[.!?])\s+', para)
                for sent in sentences:
                    sent_size = len(sent.split())
                    if current_size + sent_size > self.CHUNK_SIZE:
                        if current_chunk:
                            chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                        current_chunk = [current_chunk[-1]] if current_chunk else []
                        current_size = len(current_chunk[0].split()) if current_chunk else 0
                    current_chunk.append(sent)
                    current_size += sent_size

            elif current_size + para_size > self.CHUNK_SIZE:
                chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))
                current_chunk = [current_chunk[-1], para] if current_chunk else [para]
                current_size = sum(len(p.split()) for p in current_chunk)
            else:
                current_chunk.append(para)
                current_size += para_size

        if current_chunk:
            chunks.append(self._make_chunk(current_chunk, source_name, len(chunks)))

        return chunks

    def _make_chunk(self, parts: list[str], source: str, index: int) -> dict:
        text = "\n\n".join(p for p in parts if p)
        return {
            "text": text,
            "source": source,
            "chunk_index": index,
            "char_count": len(text)
        }

    def _clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        return text.strip()

    def _json_to_text(self, data: Any, prefix: str = "") -> str:
        if isinstance(data, dict):
            parts = []
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    parts.append(f"{prefix}{key}:")
                    parts.append(self._json_to_text(value, "  "))
                else:
                    parts.append(f"{prefix}{key}: {value}")
            return "\n".join(parts)
        elif isinstance(data, list):
            parts = []
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    parts.append(f"{prefix}[{i}]:")
                    parts.append(self._json_to_text(item, prefix + "  "))
                else:
                    parts.append(f"{prefix}- {item}")
            return "\n".join(parts)
        return str(data)

    def _read_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            return "\n\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            print("pypdf not installed - PDF support disabled")
            return ""

    def _read_docx(self, path: Path) -> str:
        try:
            from docx import Document
            doc = Document(path)
            return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except ImportError:
            print("python-docx not installed - DOCX support disabled")
            return ""

    def _read_doc(self, path: Path) -> str:
        """Read legacy .doc files using textract or antiword."""
        try:
            import textract
            text = textract.process(str(path)).decode("utf-8", errors="ignore")
            return text
        except ImportError:
            # Fallback to antiword if available
            try:
                import subprocess
                result = subprocess.run(
                    ["antiword", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    return result.stdout
            except (subprocess.SubprocessError, FileNotFoundError):
                pass
            print("textract/antiword not installed - DOC support disabled. Install with: pip install textract")
            return ""
        except Exception as e:
            print(f"Error reading DOC file: {e}")
            return ""

    def _read_odf(self, path: Path) -> str:
        """Read OpenDocument Format files (.odt, .odf)."""
        try:
            from odf import text as odf_text
            from odf.opendocument import load
            doc = load(str(path))
            paragraphs = doc.getElementsByType(odf_text.P)
            return "\n\n".join(
                "".join(node.data for node in p.childNodes if hasattr(node, "data"))
                for p in paragraphs
            )
        except ImportError:
            print("odfpy not installed - ODF support disabled. Install with: pip install odfpy")
            return ""
        except Exception as e:
            print(f"Error reading ODF file: {e}")
            return ""

    def _read_csv(self, path: Path) -> str:
        """Read CSV files and convert to readable text."""
        try:
            import csv
            with open(path, 'r', encoding='utf-8', errors='ignore', newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                return ""

            # First row as headers
            headers = rows[0] if rows else []
            content_parts = []

            for i, row in enumerate(rows[1:], start=1):
                row_text = ", ".join(
                    f"{headers[j] if j < len(headers) else f'Col{j}'}: {cell}"
                    for j, cell in enumerate(row) if cell.strip()
                )
                if row_text:
                    content_parts.append(f"Row {i}: {row_text}")

            return "\n".join(content_parts)
        except Exception as e:
            print(f"Error reading CSV file: {e}")
            return ""

    def _read_html(self, path: Path) -> str:
        """Read HTML files and extract text content."""
        try:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.skip_tags = {'script', 'style', 'head', 'meta', 'link'}
                    self.current_skip = False

                def handle_starttag(self, tag, attrs):
                    if tag.lower() in self.skip_tags:
                        self.current_skip = True

                def handle_endtag(self, tag):
                    if tag.lower() in self.skip_tags:
                        self.current_skip = False
                    if tag.lower() in ('p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'):
                        self.text_parts.append('\n')

                def handle_data(self, data):
                    if not self.current_skip:
                        text = data.strip()
                        if text:
                            self.text_parts.append(text)

            html_content = path.read_text(encoding='utf-8', errors='ignore')
            parser = TextExtractor()
            parser.feed(html_content)
            return ' '.join(parser.text_parts)
        except Exception as e:
            print(f"Error reading HTML file: {e}")
            return ""

    def _read_excel(self, path: Path) -> str:
        """Read Excel files (.xlsx, .xls) and convert to text."""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            content_parts = []

            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                content_parts.append(f"\n=== Sheet: {sheet_name} ===\n")

                rows = list(sheet.iter_rows(values_only=True))
                if not rows:
                    continue

                # First row as headers
                headers = [str(h) if h else f"Col{i}" for i, h in enumerate(rows[0])]

                for row_num, row in enumerate(rows[1:], start=1):
                    row_text = ", ".join(
                        f"{headers[j]}: {cell}"
                        for j, cell in enumerate(row)
                        if cell is not None and str(cell).strip()
                    )
                    if row_text:
                        content_parts.append(f"Row {row_num}: {row_text}")

            wb.close()
            return "\n".join(content_parts)
        except ImportError:
            print("openpyxl not installed - Excel support disabled. Install with: pip install openpyxl")
            return ""
        except Exception as e:
            print(f"Error reading Excel file: {e}")
            return ""


class InMemoryKnowledgeStore:
    """Simple in-memory knowledge store for lite mode (no OpenSearch)."""

    def __init__(self):
        self.documents: dict[str, dict] = {}  # doc_id -> doc_info
        self.chunks: list[dict] = []  # All chunks with metadata

    def add_document(self, doc_id: str, filename: str, chunks: list[dict],
                     tags: list[str], category: str) -> int:
        """Add a document and its chunks."""
        now = datetime.utcnow().isoformat()

        # Remove existing doc if re-uploading
        self.delete_document(doc_id)

        self.documents[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "tags": tags,
            "category": category,
            "indexed_at": now,
            "chunk_count": len(chunks)
        }

        for i, chunk in enumerate(chunks):
            self.chunks.append({
                "doc_id": doc_id,
                "chunk_id": f"{doc_id}_chunk_{i}",
                "filename": filename,
                "chunk_index": i,
                "text": chunk["text"],
                "tags": tags,
                "category": category,
                "indexed_at": now
            })

        return len(chunks)

    def delete_document(self, doc_id: str) -> int:
        """Delete a document and its chunks."""
        if doc_id in self.documents:
            del self.documents[doc_id]
            before = len(self.chunks)
            self.chunks = [c for c in self.chunks if c["doc_id"] != doc_id]
            return before - len(self.chunks)
        return 0

    def search(self, query: str, limit: int = 5, tags: list[str] = None,
               category: str = None) -> list[dict]:
        """Simple keyword search over chunks."""
        query_terms = set(query.lower().split())

        results = []
        for chunk in self.chunks:
            # Filter by tags/category
            if tags and not any(t in chunk["tags"] for t in tags):
                continue
            if category and chunk["category"] != category:
                continue

            # Score by keyword overlap
            chunk_terms = set(chunk["text"].lower().split())
            overlap = len(query_terms & chunk_terms)
            if overlap > 0:
                results.append({
                    **chunk,
                    "score": overlap / len(query_terms)
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def list_documents(self, category: str = None, limit: int = 50) -> list[dict]:
        """List all documents."""
        docs = list(self.documents.values())
        if category:
            docs = [d for d in docs if d["category"] == category]
        return docs[:limit]

    def get_stats(self) -> dict:
        """Get store statistics."""
        categories = {}
        tags = {}
        for chunk in self.chunks:
            cat = chunk["category"]
            categories[cat] = categories.get(cat, 0) + 1
            for tag in chunk["tags"]:
                tags[tag] = tags.get(tag, 0) + 1

        return {
            "available": True,
            "backend": "memory",
            "total_chunks": len(self.chunks),
            "unique_documents": len(self.documents),
            "categories": categories,
            "tags": tags
        }


class KnowledgeManager:
    """
    Manages RAG knowledge documents.
    
    Automatically falls back to in-memory storage if OpenSearch is unavailable.
    """

    INDEX_NAME = "icda-knowledge"

    INDEX_MAPPING = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "filename": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "chunk_index": {"type": "integer"},
                "text": {"type": "text"},
                "tags": {"type": "keyword"},
                "category": {"type": "keyword"},
                "indexed_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib"
                    }
                }
            }
        }
    }

    def __init__(self, embedder: EmbeddingClient, opensearch_client):
        self.embedder = embedder
        self.client = opensearch_client
        self.processor = DocumentProcessor()
        self.available = False
        self.use_opensearch = False

        # In-memory fallback
        self._memory_store = InMemoryKnowledgeStore()

    async def ensure_index(self) -> bool:
        """Initialize knowledge storage (OpenSearch or memory fallback)."""
        if self.client:
            try:
                if not await self.client.indices.exists(index=self.INDEX_NAME):
                    await self.client.indices.create(index=self.INDEX_NAME, body=self.INDEX_MAPPING)
                    print(f"Created knowledge index: {self.INDEX_NAME}")
                self.available = True
                self.use_opensearch = True
                return True
            except Exception as e:
                print(f"OpenSearch knowledge index failed: {e}")

        # Fallback to memory
        print("Knowledge base: Using in-memory storage (no OpenSearch)")
        self.available = True
        self.use_opensearch = False
        return True

    async def index_document(
        self,
        content: str | Path,
        filename: str = None,
        tags: list[str] = None,
        category: str = "general"
    ) -> dict:
        """Index a document into the knowledge base."""
        if not self.available:
            return {"success": False, "error": "Knowledge index not available"}

        # Process content
        if isinstance(content, Path) or (isinstance(content, str) and Path(content).exists()):
            path = Path(content)
            chunks = self.processor.process_file(path)
            filename = filename or path.name
        else:
            if not filename:
                return {"success": False, "error": "filename required for text content"}
            chunks = self.processor.process_text(content, filename)

        if not chunks:
            return {"success": False, "error": "No content extracted"}

        # Generate doc_id
        content_hash = hashlib.sha256(
            "".join(c["text"] for c in chunks).encode()
        ).hexdigest()[:12]
        doc_id = f"{Path(filename).stem}_{content_hash}"

        # Delete existing
        await self.delete_document(doc_id)

        # Use OpenSearch or memory
        if self.use_opensearch:
            return await self._index_opensearch(doc_id, filename, chunks, tags or [], category)
        else:
            indexed = self._memory_store.add_document(doc_id, filename, chunks, tags or [], category)
            return {
                "success": True,
                "doc_id": doc_id,
                "filename": filename,
                "chunks_indexed": indexed,
                "errors": 0,
                "category": category,
                "tags": tags or [],
                "backend": "memory"
            }

    async def _index_opensearch(self, doc_id: str, filename: str, chunks: list[dict],
                                  tags: list[str], category: str) -> dict:
        """Index into OpenSearch with embeddings."""
        indexed = 0
        errors = 0
        now = datetime.utcnow().isoformat()

        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            embedding = self.embedder.embed(chunk["text"]) if self.embedder else None

            doc = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "filename": filename,
                "chunk_index": i,
                "text": chunk["text"],
                "tags": tags,
                "category": category,
                "indexed_at": now,
            }

            if embedding:
                doc["embedding"] = embedding

            try:
                await self.client.index(index=self.INDEX_NAME, id=chunk_id, body=doc)
                indexed += 1
            except Exception as e:
                print(f"Index error: {e}")
                errors += 1

        await self.client.indices.refresh(index=self.INDEX_NAME)

        return {
            "success": True,
            "doc_id": doc_id,
            "filename": filename,
            "chunks_indexed": indexed,
            "errors": errors,
            "category": category,
            "tags": tags,
            "backend": "opensearch"
        }

    async def search(self, query: str, limit: int = 5, tags: list[str] = None,
                     category: str = None) -> dict:
        """Search the knowledge base."""
        if not self.available:
            return {"success": False, "hits": [], "error": "Not available"}

        if self.use_opensearch:
            return await self._search_opensearch(query, limit, tags, category)
        else:
            hits = self._memory_store.search(query, limit, tags, category)
            return {"success": True, "query": query, "hits": hits, "backend": "memory"}

    async def _search_opensearch(self, query: str, limit: int, tags: list[str],
                                   category: str) -> dict:
        """Search OpenSearch with semantic similarity."""
        embedding = self.embedder.embed(query) if self.embedder else None

        filters = []
        if tags:
            filters.append({"terms": {"tags": tags}})
        if category:
            filters.append({"term": {"category": category}})

        # Build query - semantic if embedding available, else text match
        if embedding:
            if filters:
                search_body = {
                    "size": limit,
                    "query": {
                        "bool": {
                            "filter": filters,
                            "must": [{"knn": {"embedding": {"vector": embedding, "k": limit * 2}}}]
                        }
                    }
                }
            else:
                search_body = {
                    "size": limit,
                    "query": {"knn": {"embedding": {"vector": embedding, "k": limit}}}
                }
        else:
            # Text-only fallback
            search_body = {
                "size": limit,
                "query": {
                    "bool": {
                        "must": [{"match": {"text": query}}],
                        "filter": filters if filters else None
                    }
                }
            }

        try:
            resp = await self.client.search(index=self.INDEX_NAME, body=search_body)
            hits = []
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                hits.append({
                    "doc_id": src["doc_id"],
                    "filename": src["filename"],
                    "chunk_index": src["chunk_index"],
                    "text": src["text"],
                    "category": src["category"],
                    "tags": src["tags"],
                    "score": round(hit["_score"], 4)
                })
            return {"success": True, "query": query, "hits": hits, "backend": "opensearch"}
        except Exception as e:
            return {"success": False, "hits": [], "error": str(e)}

    async def list_documents(self, category: str = None, limit: int = 50) -> list[dict]:
        """List documents in the knowledge base."""
        if not self.available:
            return []

        if not self.use_opensearch:
            return self._memory_store.list_documents(category, limit)

        agg_body: dict = {
            "size": 0,
            "aggs": {
                "documents": {
                    "terms": {"field": "doc_id", "size": limit},
                    "aggs": {
                        "doc_info": {
                            "top_hits": {
                                "size": 1,
                                "_source": ["filename", "category", "tags", "indexed_at"]
                            }
                        },
                        "chunk_count": {"value_count": {"field": "chunk_id"}}
                    }
                }
            }
        }

        if category:
            agg_body["query"] = {"term": {"category": category}}

        try:
            resp = await self.client.search(index=self.INDEX_NAME, body=agg_body)
            docs = []
            for bucket in resp["aggregations"]["documents"]["buckets"]:
                info = bucket["doc_info"]["hits"]["hits"][0]["_source"]
                docs.append({
                    "doc_id": bucket["key"],
                    "filename": info["filename"],
                    "category": info["category"],
                    "tags": info["tags"],
                    "indexed_at": info["indexed_at"],
                    "chunk_count": int(bucket["chunk_count"]["value"])
                })
            return docs
        except Exception as e:
            print(f"List error: {e}")
            return []

    async def delete_document(self, doc_id: str) -> dict:
        """Delete a document."""
        if not self.available:
            return {"deleted": 0}

        if not self.use_opensearch:
            deleted = self._memory_store.delete_document(doc_id)
            return {"deleted": deleted}

        try:
            resp = await self.client.delete_by_query(
                index=self.INDEX_NAME,
                body={"query": {"term": {"doc_id": doc_id}}}
            )
            return {"deleted": resp.get("deleted", 0)}
        except Exception as e:
            return {"deleted": 0, "error": str(e)}

    async def get_document_chunks(self, doc_id: str) -> list[dict]:
        """Get all chunks for a specific document."""
        if not self.available:
            return []

        if not self.use_opensearch:
            return [c for c in self._memory_store.chunks if c["doc_id"] == doc_id]

        try:
            resp = await self.client.search(
                index=self.INDEX_NAME,
                body={
                    "size": 1000,
                    "query": {"term": {"doc_id": doc_id}},
                    "sort": [{"chunk_index": "asc"}],
                    "_source": ["chunk_id", "chunk_index", "text", "tags", "category", "indexed_at"]
                }
            )
            chunks = []
            for hit in resp["hits"]["hits"]:
                src = hit["_source"]
                chunks.append({
                    "chunk_id": src.get("chunk_id", ""),
                    "chunk_index": src.get("chunk_index", 0),
                    "content": src.get("text", ""),
                    "tags": src.get("tags", []),
                    "category": src.get("category", "general"),
                    "created_at": src.get("indexed_at", ""),
                    "quality_score": src.get("quality_score", 1.0)
                })
            return chunks
        except Exception as e:
            print(f"Error getting document chunks: {e}")
            return []

    async def get_stats(self) -> dict:
        """Get knowledge base statistics."""
        if not self.available:
            return {"available": False}

        if not self.use_opensearch:
            return self._memory_store.get_stats()

        try:
            count = await self.client.count(index=self.INDEX_NAME)

            agg_resp = await self.client.search(
                index=self.INDEX_NAME,
                body={
                    "size": 0,
                    "aggs": {
                        "unique_docs": {"cardinality": {"field": "doc_id"}},
                        "categories": {"terms": {"field": "category", "size": 100}},
                        "tags": {"terms": {"field": "tags", "size": 100}}
                    }
                }
            )

            return {
                "available": True,
                "backend": "opensearch",
                "total_chunks": count["count"],
                "unique_documents": int(agg_resp["aggregations"]["unique_docs"]["value"]),
                "categories": {
                    b["key"]: b["doc_count"]
                    for b in agg_resp["aggregations"]["categories"]["buckets"]
                },
                "tags": {
                    b["key"]: b["doc_count"]
                    for b in agg_resp["aggregations"]["tags"]["buckets"]
                }
            }
        except Exception as e:
            return {"available": True, "backend": "opensearch", "error": str(e)}
