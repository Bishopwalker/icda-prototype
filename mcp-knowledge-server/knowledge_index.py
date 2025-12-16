"""
Knowledge Index - OpenSearch integration for document storage and retrieval.
Uses the same Titan embeddings as the main ICDA application.
"""

import json
import os
from datetime import datetime
from typing import Any

import boto3
from opensearchpy import AsyncOpenSearch, AsyncHttpConnection, AWSV4SignerAsyncAuth


class TitanEmbedder:
    """AWS Bedrock Titan Embed V2 client - matches ICDA's embeddings.py"""
    
    def __init__(self, region: str = None, model: str = None):
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.model = model or os.getenv("TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0")
        self.dimensions = 1024
        self.client = boto3.client("bedrock-runtime", region_name=self.region)
    
    def embed(self, text: str) -> list[float]:
        """Generate embedding for text."""
        try:
            resp = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps({
                    "inputText": text[:8000],  # Titan limit
                    "dimensions": self.dimensions,
                    "normalize": True
                })
            )
            return json.loads(resp["body"].read())["embedding"]
        except Exception as e:
            print(f"Embedding error: {e}")
            return []


class KnowledgeIndex:
    """
    OpenSearch index for knowledge documents.
    
    Schema:
      - doc_id: unique document identifier
      - chunk_id: unique chunk identifier  
      - filename: original filename
      - chunk_index: position in document
      - text: chunk content
      - embedding: Titan 1024-dim vector
      - tags: list of tags
      - category: document category
      - source_path: original file path
      - indexed_at: timestamp
    """
    
    INDEX_MAPPING = {
        "settings": {
            "index": {
                "knn": True,
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        },
        "mappings": {
            "properties": {
                "doc_id": {"type": "keyword"},
                "chunk_id": {"type": "keyword"},
                "filename": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "chunk_index": {"type": "integer"},
                "text": {"type": "text"},
                "tags": {"type": "keyword"},
                "category": {"type": "keyword"},
                "source_path": {"type": "keyword"},
                "indexed_at": {"type": "date"},
                "embedding": {
                    "type": "knn_vector",
                    "dimension": 1024,
                    "method": {
                        "name": "hnsw",
                        "space_type": "cosinesimil",
                        "engine": "nmslib",
                        "parameters": {
                            "ef_construction": 128,
                            "m": 24
                        }
                    }
                }
            }
        }
    }
    
    def __init__(self, index_name: str):
        self.index = index_name
        self.client: AsyncOpenSearch | None = None
        self.embedder = TitanEmbedder()
        self.available = False
    
    async def connect(self) -> None:
        """Connect to OpenSearch."""
        host = os.getenv("OPENSEARCH_HOST", "")
        region = os.getenv("AWS_REGION", "us-east-1")
        
        if not host:
            # Try local OpenSearch
            host = "localhost:9200"
            print(f"No OPENSEARCH_HOST set, trying local: {host}")
        
        is_aws = "amazonaws.com" in host
        is_serverless = "aoss.amazonaws.com" in host
        
        try:
            if is_aws:
                credentials = boto3.Session().get_credentials()
                service = "aoss" if is_serverless else "es"
                self.client = AsyncOpenSearch(
                    hosts=[{"host": host, "port": 443}],
                    http_auth=AWSV4SignerAsyncAuth(credentials, region, service),
                    use_ssl=True,
                    verify_certs=True,
                    connection_class=AsyncHttpConnection
                )
            else:
                # Local connection
                clean_host = host.replace("localhost", "127.0.0.1")
                if not clean_host.startswith("http"):
                    clean_host = f"http://{clean_host}"
                self.client = AsyncOpenSearch(
                    hosts=[clean_host],
                    use_ssl=False,
                    verify_certs=False,
                    connection_class=AsyncHttpConnection
                )
            
            # Test connection
            await self.client.info()
            self.available = True
            print(f"✅ Connected to OpenSearch: {host}")
            
            # Ensure index exists
            await self._ensure_index()
            
        except Exception as e:
            print(f"❌ OpenSearch connection failed: {e}")
            self.available = False
    
    async def _ensure_index(self) -> None:
        """Create index if it doesn't exist."""
        if not await self.client.indices.exists(index=self.index):
            await self.client.indices.create(index=self.index, body=self.INDEX_MAPPING)
            print(f"Created knowledge index: {self.index}")
    
    async def close(self) -> None:
        """Close connection."""
        if self.client:
            await self.client.close()
    
    async def index_document(
        self,
        doc_id: str,
        filename: str,
        chunks: list[dict],
        tags: list[str],
        category: str,
        source_path: str
    ) -> dict:
        """
        Index a document's chunks.
        
        Args:
            doc_id: Unique document identifier
            filename: Original filename
            chunks: List of {"text": str, "metadata": dict}
            tags: List of tags
            category: Document category
            source_path: Original file path
            
        Returns:
            {"indexed": int, "errors": int}
        """
        if not self.available:
            return {"indexed": 0, "errors": 0, "message": "OpenSearch not available"}
        
        # Delete existing chunks for this doc_id (for re-uploads)
        await self.delete_document(doc_id)
        
        indexed = 0
        errors = 0
        now = datetime.utcnow().isoformat()
        
        for i, chunk in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{i}"
            text = chunk["text"]
            
            # Generate embedding
            embedding = self.embedder.embed(text)
            if not embedding:
                errors += 1
                continue
            
            doc = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "filename": filename,
                "chunk_index": i,
                "text": text,
                "tags": tags,
                "category": category,
                "source_path": source_path,
                "indexed_at": now,
                "embedding": embedding
            }
            
            try:
                await self.client.index(
                    index=self.index,
                    id=chunk_id,
                    body=doc
                )
                indexed += 1
            except Exception as e:
                print(f"Index error for {chunk_id}: {e}")
                errors += 1
        
        # Refresh to make searchable
        await self.client.indices.refresh(index=self.index)
        
        return {"indexed": indexed, "errors": errors}
    
    async def search(
        self,
        query: str,
        limit: int = 5,
        tags: list[str] | None = None,
        category: str | None = None
    ) -> dict:
        """
        Semantic search over knowledge base.
        
        Args:
            query: Natural language query
            limit: Max results
            tags: Filter by tags (optional)
            category: Filter by category (optional)
            
        Returns:
            {"hits": [...], "total": int}
        """
        if not self.available:
            return {"hits": [], "total": 0}
        
        embedding = self.embedder.embed(query)
        if not embedding:
            return {"hits": [], "total": 0, "error": "Failed to embed query"}
        
        # Build filter
        filters = []
        if tags:
            filters.append({"terms": {"tags": tags}})
        if category:
            filters.append({"term": {"category": category}})
        
        # KNN query
        if filters:
            search_body = {
                "size": limit,
                "query": {
                    "bool": {
                        "filter": filters,
                        "must": [
                            {"knn": {"embedding": {"vector": embedding, "k": limit * 2}}}
                        ]
                    }
                }
            }
        else:
            search_body = {
                "size": limit,
                "query": {
                    "knn": {"embedding": {"vector": embedding, "k": limit}}
                }
            }
        
        try:
            resp = await self.client.search(index=self.index, body=search_body)
            hits = []
            for hit in resp["hits"]["hits"]:
                source = hit["_source"]
                hits.append({
                    "doc_id": source["doc_id"],
                    "filename": source["filename"],
                    "chunk_index": source["chunk_index"],
                    "text": source["text"],
                    "category": source["category"],
                    "tags": source["tags"],
                    "score": round(hit["_score"], 4)
                })
            
            return {
                "hits": hits,
                "total": resp["hits"]["total"]["value"]
            }
        except Exception as e:
            return {"hits": [], "total": 0, "error": str(e)}
    
    async def list_documents(
        self,
        category: str | None = None,
        limit: int = 50
    ) -> list[dict]:
        """List unique documents (aggregated by doc_id)."""
        if not self.available:
            return []
        
        # Aggregation to get unique documents
        agg_body: dict[str, Any] = {
            "size": 0,
            "aggs": {
                "documents": {
                    "terms": {
                        "field": "doc_id",
                        "size": limit
                    },
                    "aggs": {
                        "doc_info": {
                            "top_hits": {
                                "size": 1,
                                "_source": ["filename", "category", "tags", "source_path", "indexed_at"]
                            }
                        },
                        "chunk_count": {
                            "value_count": {"field": "chunk_id"}
                        }
                    }
                }
            }
        }
        
        if category:
            agg_body["query"] = {"term": {"category": category}}
        
        try:
            resp = await self.client.search(index=self.index, body=agg_body)
            docs = []
            for bucket in resp["aggregations"]["documents"]["buckets"]:
                info = bucket["doc_info"]["hits"]["hits"][0]["_source"]
                docs.append({
                    "doc_id": bucket["key"],
                    "filename": info["filename"],
                    "category": info["category"],
                    "tags": info["tags"],
                    "source_path": info["source_path"],
                    "indexed_at": info["indexed_at"],
                    "chunk_count": bucket["chunk_count"]["value"]
                })
            return docs
        except Exception as e:
            print(f"List documents error: {e}")
            return []
    
    async def delete_document(self, doc_id: str) -> dict:
        """Delete all chunks for a document."""
        if not self.available:
            return {"deleted": 0}
        
        try:
            resp = await self.client.delete_by_query(
                index=self.index,
                body={"query": {"term": {"doc_id": doc_id}}}
            )
            return {"deleted": resp.get("deleted", 0)}
        except Exception as e:
            print(f"Delete error: {e}")
            return {"deleted": 0, "error": str(e)}
    
    async def get_stats(self) -> dict:
        """Get index statistics."""
        if not self.available:
            return {"available": False}
        
        try:
            # Count documents and chunks
            count_resp = await self.client.count(index=self.index)
            
            # Get index stats
            stats_resp = await self.client.indices.stats(index=self.index)
            index_stats = stats_resp["indices"][self.index]["primaries"]
            
            # Count unique documents
            agg_resp = await self.client.search(
                index=self.index,
                body={
                    "size": 0,
                    "aggs": {
                        "unique_docs": {"cardinality": {"field": "doc_id"}},
                        "categories": {"terms": {"field": "category", "size": 100}}
                    }
                }
            )
            
            categories = {
                b["key"]: b["doc_count"] 
                for b in agg_resp["aggregations"]["categories"]["buckets"]
            }
            
            return {
                "available": True,
                "total_chunks": count_resp["count"],
                "unique_documents": agg_resp["aggregations"]["unique_docs"]["value"],
                "index_size_bytes": index_stats["store"]["size_in_bytes"],
                "categories": categories
            }
        except Exception as e:
            return {"available": True, "error": str(e)}
    
    async def reindex_all(self) -> dict:
        """Delete and recreate index (use with caution!)."""
        if not self.available:
            return {"error": "OpenSearch not available"}
        
        try:
            # Get all documents first
            docs = await self.list_documents(limit=1000)
            
            # Delete index
            if await self.client.indices.exists(index=self.index):
                await self.client.indices.delete(index=self.index)
            
            # Recreate
            await self._ensure_index()
            
            return {
                "index_recreated": True,
                "previous_documents": len(docs),
                "note": "Documents must be re-uploaded"
            }
        except Exception as e:
            return {"error": str(e)}
