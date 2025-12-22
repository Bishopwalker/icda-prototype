"""Index Manager - Coordinates auto-indexing when data changes.

Listens for data source changes and triggers:
1. Address index rebuild
2. ZIP database rebuild  
3. OpenSearch vector index update
4. Cache invalidation
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from .datasource import DataSource, DataSourceMetadata, DataChangeListener

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexStats:
    """Statistics about indexing operations."""
    addresses_indexed: int = 0
    zips_indexed: int = 0
    vectors_indexed: int = 0
    last_index_time_ms: int = 0
    index_errors: list[str] = None
    
    def __post_init__(self):
        if self.index_errors is None:
            self.index_errors = []


class IndexManager(DataChangeListener):
    """Manages automatic indexing when data changes.
    
    Usage:
        data_source = JSONFileDataSource("customers.json")
        index_manager = IndexManager(
            address_index=address_index,
            zip_database=zip_database,
            vector_index=vector_index,
            cache=cache,
        )
        data_source.add_listener(index_manager)
        await data_source.load()  # Triggers initial indexing
    """
    
    def __init__(
        self,
        address_index=None,
        zip_database=None,
        vector_index=None,
        address_vector_index=None,
        cache=None,
        auto_index: bool = True,
    ):
        """Initialize IndexManager.
        
        Args:
            address_index: AddressIndex instance for address lookups
            zip_database: ZipDatabase instance for ZIP validation
            vector_index: VectorIndex instance for OpenSearch
            address_vector_index: AddressVectorIndex for address semantic search
            cache: RedisCache instance to clear on data change
            auto_index: Whether to auto-index on data change (default True)
        """
        self._address_index = address_index
        self._zip_database = zip_database
        self._vector_index = vector_index
        self._address_vector_index = address_vector_index
        self._cache = cache
        self._auto_index = auto_index
        self._stats = IndexStats()
        self._indexing_lock = asyncio.Lock()
    
    @property
    def stats(self) -> IndexStats:
        """Get indexing statistics."""
        return self._stats
    
    async def on_data_changed(self, source: DataSource, metadata: DataSourceMetadata) -> None:
        """Called when data source changes - triggers re-indexing."""
        if not self._auto_index:
            logger.info("Auto-indexing disabled, skipping re-index")
            return
        
        logger.info(f"Data source changed: {metadata.total_records} records from {metadata.source_type}")
        await self.reindex_all(source.customers)
    
    async def reindex_all(self, customers: list[dict]) -> IndexStats:
        """Reindex all indexes with new customer data.
        
        Args:
            customers: List of customer records
            
        Returns:
            IndexStats with results
        """
        import time
        start = time.perf_counter()
        
        async with self._indexing_lock:
            self._stats = IndexStats()
            
            # Clear cache first
            if self._cache:
                try:
                    await self._cache.clear()
                    logger.info("Cache cleared")
                except Exception as e:
                    self._stats.index_errors.append(f"Cache clear failed: {e}")
            
            # Rebuild address index
            if self._address_index:
                try:
                    self._address_index.build_from_customers(customers)
                    self._stats.addresses_indexed = getattr(self._address_index, "total_addresses", len(customers))
                    logger.info(f"Address index rebuilt: {self._stats.addresses_indexed} addresses")
                except Exception as e:
                    logger.error(f"Address index failed: {e}")
                    self._stats.index_errors.append(f"Address index: {e}")
            
            # Rebuild ZIP database
            if self._zip_database:
                try:
                    self._zip_database.build_from_customers(customers)
                    self._stats.zips_indexed = getattr(self._zip_database, "total_zips", 0)
                    logger.info(f"ZIP database rebuilt: {self._stats.zips_indexed} ZIPs")
                except Exception as e:
                    logger.error(f"ZIP database failed: {e}")
                    self._stats.index_errors.append(f"ZIP database: {e}")
            
            # Rebuild vector index (async)
            if self._vector_index and getattr(self._vector_index, "available", False):
                try:
                    count = await self._vector_index.index_customers(customers)
                    self._stats.vectors_indexed = count
                    logger.info(f"Vector index rebuilt: {count} vectors")
                except Exception as e:
                    logger.error(f"Vector index failed: {e}")
                    self._stats.index_errors.append(f"Vector index: {e}")
            
            # Rebuild address vector index (async)
            if self._address_vector_index and getattr(self._address_vector_index, "available", False):
                try:
                    # Address vector index might have a different API
                    if hasattr(self._address_vector_index, "index_addresses"):
                        await self._address_vector_index.index_addresses(customers)
                except Exception as e:
                    logger.error(f"Address vector index failed: {e}")
                    self._stats.index_errors.append(f"Address vector index: {e}")
            
            self._stats.last_index_time_ms = int((time.perf_counter() - start) * 1000)
            logger.info(f"Reindexing complete in {self._stats.last_index_time_ms}ms")
            
            return self._stats
    
    async def index_customers_only(self, customers: list[dict]) -> int:
        """Index only the vector index (faster for incremental updates)."""
        if not self._vector_index or not getattr(self._vector_index, "available", False):
            return 0
        
        try:
            return await self._vector_index.index_customers(customers)
        except Exception as e:
            logger.error(f"Customer vector indexing failed: {e}")
            return 0


class DataSourceWatcher:
    """Watches data sources for changes and triggers reloading.
    
    Supports:
    - File-based sources (JSON, CSV): Polls for file modification
    - Database sources: Can use change streams or polling
    """
    
    def __init__(
        self,
        data_source: DataSource,
        poll_interval: float = 30.0,
    ):
        """Initialize watcher.
        
        Args:
            data_source: DataSource to watch
            poll_interval: Seconds between polls for file-based sources
        """
        self._source = data_source
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task | None = None
    
    def start(self) -> None:
        """Start watching for changes."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(f"Started watching data source (poll interval: {self._poll_interval}s)")
    
    def stop(self) -> None:
        """Stop watching."""
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None
        logger.info("Stopped watching data source")
    
    async def _watch_loop(self) -> None:
        """Main watch loop."""
        while self._running:
            try:
                await asyncio.sleep(self._poll_interval)
                
                # Check if source has a check_for_changes method
                if hasattr(self._source, "check_for_changes"):
                    if self._source.check_for_changes():
                        logger.info("Data source change detected, reloading...")
                        await self._source.reload()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Watch loop error: {e}")
