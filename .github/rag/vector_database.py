"""
Universal Cloud Vector Database - Multi-Provider Support
Easily switch between local ChromaDB, Pinecone, Weaviate, or custom solutions
Domain-agnostic vector storage for any codebase
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
from enum import Enum

# Base imports
from sentence_transformers import SentenceTransformer
try:
    from .chunking_strategy import CodeChunk
except ImportError:
    from chunking_strategy import CodeChunk

class VectorProvider(Enum):
    """Supported vector database providers"""
    CHROMA = "chroma"
    SUPABASE = "supabase"  # Added by Agent 3
    PINECONE = "pinecone"
    WEAVIATE = "weaviate"
    QDRANT = "qdrant"
    OPENSEARCH = "opensearch"

class BaseVectorDatabase(ABC):
    """Abstract base class for vector databases"""

    def __init__(self, embedding_model: str = "all-MiniLM-L6-v2"):
        self.embedder = SentenceTransformer(embedding_model)

    @abstractmethod
    def add_chunks(self, chunks: List[CodeChunk], batch_size: int = 100):
        """Add chunks to the vector database"""
        pass

    @abstractmethod
    def search(self, query: str, n_results: int = 5, filter_dict: Optional[Dict] = None):
        """Search for relevant chunks"""
        pass

    @abstractmethod
    def clear_database(self):
        """Clear all data from the database"""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the database"""
        pass

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        embedding = self.embedder.encode(text, convert_to_tensor=False)
        return embedding.tolist()

class ChromaVectorDatabase(BaseVectorDatabase):
    """Local ChromaDB implementation"""

    def __init__(
        self,
        persist_directory: str = "./.github/rag/chroma_db",
        collection_name: str = "code_chunks",
        **kwargs
    ):
        super().__init__(**kwargs)
        import chromadb
        from chromadb.config import Settings

        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name
        )

    def add_chunks(self, chunks: List[CodeChunk], batch_size: int = 100):
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            ids = [chunk.id for chunk in batch]
            embeddings = [self.generate_embedding(chunk.content) for chunk in batch]
            documents = [chunk.content for chunk in batch]
            metadatas = [self._prepare_metadata(chunk) for chunk in batch]

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )

    def search(self, query: str, n_results: int = 5, filter_dict: Optional[Dict] = None):
        query_embedding = self.generate_embedding(query)

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_dict,
            include=["documents", "metadatas", "distances"]
        )

        return self._format_results(results, query)

    def clear_database(self):
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.create_collection(self.collection_name)

    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_documents': self.collection.count(),
            'provider': 'ChromaDB (Local)'
        }

    def _prepare_metadata(self, chunk: CodeChunk) -> Dict:
        return {
            "file_path": chunk.file_path,
            "chunk_type": chunk.chunk_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            **chunk.metadata
        }

    def _format_results(self, results, query):
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                'id': results['ids'][0][i],
                'content': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i],
                'similarity_score': 1 - results['distances'][0][i]
            })
        return {'query': query, 'results': formatted}


class SupabaseVectorDatabase(BaseVectorDatabase):
    """
    Supabase (PostgreSQL + pgvector) implementation
    Cloud-based vector storage with pgvector extension
    """

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        table_name: str = "code_chunks",
        **kwargs
    ):
        """
        Initialize Supabase vector database

        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key (anon or service role)
            table_name: Table name for storing vectors
            **kwargs: Additional arguments (embedding_model, etc.)
        """
        super().__init__(**kwargs)

        try:
            from supabase import create_client, Client
        except ImportError:
            raise ImportError(
                "supabase package not installed. Install with: pip install supabase"
            )

        self.client: Client = create_client(supabase_url, supabase_key)
        self.table_name = table_name

        # Initialize table if needed
        self._ensure_table_exists()

    def _ensure_table_exists(self):
        """
        Ensure the vector table exists with proper schema

        Table schema:
        - id: text (primary key)
        - content: text (the code chunk)
        - embedding: vector(384) (sentence transformer embedding)
        - metadata: jsonb (file_path, chunk_type, etc.)
        - created_at: timestamp

        Note: Table must be created manually in Supabase with pgvector extension
        See SETUP.md for detailed instructions
        """
        # Reason: We check if table exists to provide helpful error messages
        # Actual table creation must be done in Supabase console
        try:
            # Test if table exists by querying it
            self.client.table(self.table_name).select("id").limit(1).execute()
        except Exception as e:
            raise RuntimeError(
                f"Table '{self.table_name}' not found or not accessible. "
                f"Please create it in Supabase with pgvector extension. "
                f"See .github/rag/SETUP.md for instructions. Error: {e}"
            )

    def add_chunks(self, chunks: List[CodeChunk], batch_size: int = 100):
        """Add chunks to Supabase vector database"""
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            # Prepare data for insertion
            records = []
            for chunk in batch:
                embedding = self.generate_embedding(chunk.content)
                record = {
                    "id": chunk.id,
                    "content": chunk.content,
                    "embedding": embedding,
                    "metadata": {
                        "file_path": chunk.file_path,
                        "chunk_type": chunk.chunk_type,
                        "start_line": chunk.start_line,
                        "end_line": chunk.end_line,
                        **chunk.metadata
                    }
                }
                records.append(record)

            # Insert batch
            try:
                self.client.table(self.table_name).upsert(records).execute()
            except Exception as e:
                print(f"Warning: Failed to insert batch {i}-{i+batch_size}: {e}")

    def search(self, query: str, n_results: int = 5, filter_dict: Optional[Dict] = None):
        """
        Search for relevant chunks using pgvector similarity

        Args:
            query: Search query
            n_results: Number of results to return
            filter_dict: Optional metadata filters

        Returns:
            Dictionary with query and results
        """
        query_embedding = self.generate_embedding(query)

        # Build the query
        # Note: This uses pgvector's <-> operator for cosine distance
        rpc_params = {
            "query_embedding": query_embedding,
            "match_count": n_results
        }

        # Add metadata filters if provided
        if filter_dict:
            rpc_params["filter"] = filter_dict

        try:
            # Call the vector search RPC function
            # This function must be created in Supabase (see SETUP.md)
            response = self.client.rpc(
                "match_code_chunks",
                rpc_params
            ).execute()

            results = response.data if response.data else []

            # Format results to match ChromaDB output format
            formatted = []
            for result in results:
                formatted.append({
                    'id': result.get('id'),
                    'content': result.get('content'),
                    'metadata': result.get('metadata', {}),
                    'distance': result.get('distance', 0),
                    'similarity_score': 1 - result.get('distance', 0)
                })

            return {'query': query, 'results': formatted}

        except Exception as e:
            print(f"Warning: Supabase search failed: {e}")
            return {'query': query, 'results': []}

    def clear_database(self):
        """Clear all data from the database"""
        try:
            # Delete all rows
            self.client.table(self.table_name).delete().neq("id", "").execute()
        except Exception as e:
            print(f"Warning: Failed to clear database: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the database"""
        try:
            # Count total documents
            response = self.client.table(self.table_name).select(
                "id",
                count="exact"
            ).execute()

            total = response.count if hasattr(response, 'count') else 0

            return {
                'total_documents': total,
                'provider': 'Supabase (Cloud)',
                'table': self.table_name
            }
        except Exception as e:
            return {
                'total_documents': 0,
                'provider': 'Supabase (Cloud)',
                'table': self.table_name,
                'error': str(e)
            }

class VectorDatabaseFactory:
    """Factory to create the appropriate vector database"""

    @staticmethod
    def create(provider: VectorProvider, **config) -> BaseVectorDatabase:
        """
        Create a vector database instance

        Args:
            provider: Which provider to use
            **config: Provider-specific configuration

        Returns:
            Vector database instance
        """
        if provider == VectorProvider.CHROMA:
            return ChromaVectorDatabase(**config)
        elif provider == VectorProvider.SUPABASE:
            # Added by Agent 3: Supabase cloud vector storage
            return SupabaseVectorDatabase(**config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

class CloudRAGPipeline:
    """
    Unified RAG pipeline that works with any vector database provider
    """

    def __init__(self,
                 project_root: str,
                 provider: VectorProvider = VectorProvider.CHROMA,
                 **vector_config):
        """
        Initialize RAG pipeline with specified provider

        Args:
            project_root: Root directory of your project
            provider: Which vector database to use
            **vector_config: Provider-specific configuration
        """
        try:
            from .chunking_strategy import EBLChunkingStrategy
        except ImportError:
            from chunking_strategy import EBLChunkingStrategy

        self.project_root = project_root
        self.chunker = EBLChunkingStrategy(project_root)
        self.provider = provider

        # Create vector database
        self.vector_db = VectorDatabaseFactory.create(provider, **vector_config)

    def index_project(self, force_reindex: bool = False):
        """Index the entire project"""
        stats = self.vector_db.get_stats()

        if not force_reindex and stats['total_documents'] > 0:
            return

        if force_reindex:
            self.vector_db.clear_database()

        # Chunk and index
        chunks = self.chunker.chunk_project()

        self.vector_db.add_chunks(chunks)

    def query(self, query: str, n_results: int = 5):
        """Query the RAG system"""
        return self.vector_db.search(query, n_results)

if __name__ == "__main__":
    # Example: Start with local ChromaDB
    local_rag = CloudRAGPipeline(
        project_root="./your-project-root",
        provider=VectorProvider.CHROMA
    )
    local_rag.index_project()

    # Test local search
    results = local_rag.query("database connection pool")