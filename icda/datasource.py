"""Data Source Abstraction Layer.

Provides a unified interface for loading customer data from multiple sources:
- JSON files
- PostgreSQL
- MongoDB
- REST APIs
- CSV files

Auto-detects available states, cities, and other metadata from the data itself.
Triggers re-indexing when data changes.
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Protocol
from bisect import bisect_left

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DataSourceMetadata:
    """Metadata about the loaded data source.
    
    Auto-populated from the actual data, not hardcoded.
    """
    total_records: int = 0
    available_states: list[str] = field(default_factory=list)
    state_counts: dict[str, int] = field(default_factory=dict)
    available_cities: list[str] = field(default_factory=list)
    customer_types: list[str] = field(default_factory=list)
    date_range: tuple[str, str] | None = None
    last_updated: str | None = None
    source_type: str = "unknown"
    source_uri: str = ""
    
    def has_state(self, state: str) -> bool:
        """Check if state exists in the data."""
        return state.upper() in self.available_states
    
    def get_state_name(self, code: str) -> str:
        """Get full state name from code."""
        return STATE_CODE_TO_NAME.get(code.upper(), code)


# State code to name mapping (could also be loaded dynamically)
STATE_CODE_TO_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
    "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington DC",
}

STATE_NAME_TO_CODE = {v.lower(): k for k, v in STATE_CODE_TO_NAME.items()}


class DataChangeListener(Protocol):
    """Protocol for data change notifications."""
    
    async def on_data_changed(self, source: "DataSource", metadata: DataSourceMetadata) -> None:
        """Called when data source changes."""
        ...


class DataSource(ABC):
    """Abstract base class for customer data sources.
    
    Implementations must provide:
    - load(): Load all data
    - lookup(crid): Find single customer
    - search(...): Search with filters
    - stream(): Async iterate over records (for large datasets)
    - watch(): Monitor for changes
    """
    
    def __init__(self):
        self._metadata: DataSourceMetadata | None = None
        self._listeners: list[DataChangeListener] = []
        self._customers: list[dict] = []
        self._by_crid: dict[str, dict] = {}
        self._by_state: dict[str, list[dict]] = {}
        # Autocomplete indexes
        self._address_index: list[tuple[str, dict]] = []
        self._name_index: list[tuple[str, dict]] = []
        self._city_index: list[tuple[str, dict]] = []
    
    @property
    def metadata(self) -> DataSourceMetadata:
        """Get data source metadata (auto-populated from data)."""
        if self._metadata is None:
            self._metadata = DataSourceMetadata()
        return self._metadata
    
    @property
    def customers(self) -> list[dict]:
        """Get all loaded customers."""
        return self._customers
    
    @property
    def by_crid(self) -> dict[str, dict]:
        """Get customers indexed by CRID."""
        return self._by_crid
    
    @property
    def by_state(self) -> dict[str, list[dict]]:
        """Get customers indexed by state."""
        return self._by_state
    
    def add_listener(self, listener: DataChangeListener) -> None:
        """Add a data change listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: DataChangeListener) -> None:
        """Remove a data change listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    async def _notify_listeners(self) -> None:
        """Notify all listeners of data change."""
        for listener in self._listeners:
            try:
                await listener.on_data_changed(self, self.metadata)
            except Exception as e:
                logger.warning(f"Listener notification failed: {e}")
    
    def _build_metadata(self) -> DataSourceMetadata:
        """Build metadata from loaded data."""
        metadata = DataSourceMetadata()
        metadata.total_records = len(self._customers)
        
        # Count by state
        state_counts: dict[str, int] = {}
        cities: set[str] = set()
        customer_types: set[str] = set()
        dates: list[str] = []
        
        for customer in self._customers:
            state = customer.get("state", "").upper()
            if state:
                state_counts[state] = state_counts.get(state, 0) + 1
            
            city = customer.get("city", "")
            if city:
                cities.add(city)
            
            ctype = customer.get("customer_type", "")
            if ctype:
                customer_types.add(ctype)
            
            created = customer.get("created_date")
            if created:
                dates.append(created)
        
        # Sort states by count descending
        sorted_states = sorted(state_counts.items(), key=lambda x: x[1], reverse=True)
        metadata.available_states = [s for s, _ in sorted_states]
        metadata.state_counts = state_counts
        metadata.available_cities = sorted(cities)
        metadata.customer_types = sorted(customer_types)
        
        if dates:
            metadata.date_range = (min(dates), max(dates))
        
        return metadata
    
    def _build_indexes(self) -> None:
        """Build internal indexes for fast lookups."""
        # CRID index
        self._by_crid = {c["crid"]: c for c in self._customers if "crid" in c}
        
        # State index
        self._by_state = {}
        for c in self._customers:
            state = c.get("state", "").upper()
            if state:
                self._by_state.setdefault(state, []).append(c)
        
        # Autocomplete indexes
        self._address_index = sorted(
            [(c["address"].lower(), c) for c in self._customers if c.get("address")],
            key=lambda x: x[0]
        )
        self._name_index = sorted(
            [(c["name"].lower(), c) for c in self._customers if c.get("name")],
            key=lambda x: x[0]
        )
        self._city_index = sorted(
            [(c["city"].lower(), c) for c in self._customers if c.get("city")],
            key=lambda x: x[0]
        )
        
        logger.info(f"Built indexes: {len(self._by_crid)} CRIDs, {len(self._by_state)} states")
    
    @abstractmethod
    async def load(self) -> None:
        """Load data from source. Must call _build_metadata() and _build_indexes()."""
        ...
    
    @abstractmethod
    async def reload(self) -> None:
        """Reload data from source (for watching changes)."""
        ...
    
    def lookup(self, crid: str) -> dict:
        """Look up customer by CRID."""
        crid = crid.upper()
        if crid.startswith("CRID-"):
            num = crid.removeprefix("CRID-")
            for fmt in (f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(5)}", f"CRID-{num.zfill(3)}", crid):
                if data := self._by_crid.get(fmt):
                    return {"success": True, "data": data}
        return {"success": False, "error": f"CRID {crid} not found"}
    
    def search(
        self,
        state: str = None,
        city: str = None,
        min_moves: int = None,
        customer_type: str = None,
        has_apartment: bool = None,
        limit: int = None,
    ) -> dict:
        """Search customers with filters."""
        # Validate state if provided
        if state:
            state_upper = state.upper()
            if state_upper not in self._by_state:
                # State not in data - return helpful error
                return {
                    "success": False,
                    "error": "state_not_available",
                    "requested_state": state_upper,
                    "requested_state_name": STATE_CODE_TO_NAME.get(state_upper, state),
                    "available_states": self.metadata.available_states,
                    "available_states_with_counts": self.metadata.state_counts,
                    "suggestion": f"{STATE_CODE_TO_NAME.get(state_upper, state)} is not in our database. "
                                  f"We have data for {len(self.metadata.available_states)} states.",
                }
            results = self._by_state.get(state_upper, [])
        else:
            results = self._customers
        
        # Apply filters
        if min_moves:
            results = [c for c in results if c.get("move_count", 0) >= min_moves]
        if city:
            city_lower = city.casefold()
            results = [c for c in results if city_lower in c.get("city", "").casefold()]
        if customer_type:
            ct_upper = customer_type.upper()
            results = [c for c in results if c.get("customer_type", "").upper() == ct_upper]
        if has_apartment:
            results = [c for c in results if 
                       "apt" in c.get("address", "").lower() or 
                       "unit" in c.get("address", "").lower()]
        
        data = results[:limit] if limit else results
        return {"success": True, "total": len(results), "data": data}
    
    def stats(self) -> dict:
        """Get statistics about the data."""
        return {
            "success": True,
            "data": self.metadata.state_counts,
            "total": self.metadata.total_records,
            "states": len(self.metadata.available_states),
            "source_type": self.metadata.source_type,
        }
    
    def has_state(self, state: str) -> bool:
        """Check if state exists in data."""
        return state.upper() in self._by_state
    
    def get_available_states(self) -> list[str]:
        """Get list of available states."""
        return self.metadata.available_states
    
    def get_state_counts(self) -> dict[str, int]:
        """Get customer counts per state."""
        return self.metadata.state_counts
    
    def autocomplete(self, field: str, prefix: str, limit: int = 10) -> dict:
        """Fast prefix-based autocomplete using binary search."""
        prefix_lower = prefix.lower().strip()
        if not prefix_lower:
            return {"success": False, "error": "Empty prefix"}
        
        index = {
            "address": self._address_index,
            "name": self._name_index,
            "city": self._city_index,
        }.get(field)
        
        if not index:
            return {"success": False, "error": f"Unknown field: {field}"}
        
        pos = bisect_left(index, (prefix_lower,))
        results = []
        seen_values = set()
        
        while pos < len(index) and len(results) < limit:
            value, customer = index[pos]
            if not value.startswith(prefix_lower):
                break
            
            if field == "city":
                city_key = customer["city"].lower()
                if city_key not in seen_values:
                    seen_values.add(city_key)
                    results.append({
                        "value": customer["city"],
                        "state": customer["state"],
                        "count": sum(1 for c in self._customers if c.get("city", "").lower() == city_key)
                    })
            else:
                results.append({
                    "crid": customer["crid"],
                    "value": customer[field],
                    "name": customer["name"],
                    "city": customer["city"],
                    "state": customer["state"],
                })
            pos += 1
        
        return {"success": True, "field": field, "prefix": prefix, "count": len(results), "data": results}
    
    def autocomplete_fuzzy(self, field: str, query: str, limit: int = 10) -> dict:
        """Fuzzy autocomplete for typo tolerance."""
        query_lower = query.lower().strip()
        if len(query_lower) < 2:
            return {"success": False, "error": "Query too short"}
        
        if field not in ("address", "name", "city"):
            return {"success": False, "error": f"Unknown field: {field}"}
        
        def similarity(text: str) -> float:
            text_lower = text.lower()
            if text_lower.startswith(query_lower):
                return 1.0 + len(query_lower) / len(text_lower)
            if query_lower in text_lower:
                return 0.8
            words = text_lower.split()
            if any(w.startswith(query_lower) for w in words):
                return 0.7
            query_chars = set(query_lower)
            text_chars = set(text_lower)
            overlap = len(query_chars & text_chars) / len(query_chars)
            return overlap * 0.5 if overlap > 0.6 else 0
        
        scored = []
        seen = set()
        for c in self._customers:
            value = c.get(field, "")
            if not value:
                continue
            score = similarity(value)
            if score > 0.4 and value.lower() not in seen:
                seen.add(value.lower())
                scored.append((score, c))
        
        scored.sort(key=lambda x: -x[0])
        results = [
            {"crid": c["crid"], "value": c[field], "name": c["name"],
             "city": c["city"], "state": c["state"], "score": round(s, 2)}
            for s, c in scored[:limit]
        ]
        
        return {"success": True, "field": field, "query": query, "count": len(results), "data": results}


class JSONFileDataSource(DataSource):
    """Load customer data from a JSON file."""
    
    def __init__(self, filepath: Path | str):
        super().__init__()
        self._filepath = Path(filepath)
        self._last_mtime: float = 0
    
    async def load(self) -> None:
        """Load data from JSON file."""
        if not self._filepath.exists():
            logger.warning(f"Data file not found: {self._filepath}")
            self._customers = []
            self._metadata = self._build_metadata()
            self._metadata.source_type = "json_file"
            self._metadata.source_uri = str(self._filepath)
            return
        
        try:
            data = json.loads(self._filepath.read_text(encoding="utf-8"))
            self._customers = data if isinstance(data, list) else []
            self._last_mtime = self._filepath.stat().st_mtime
            
            self._build_indexes()
            self._metadata = self._build_metadata()
            self._metadata.source_type = "json_file"
            self._metadata.source_uri = str(self._filepath)
            
            logger.info(f"Loaded {len(self._customers)} customers from {self._filepath}")
            
        except Exception as e:
            logger.error(f"Failed to load data from {self._filepath}: {e}")
            self._customers = []
            self._metadata = self._build_metadata()
    
    async def reload(self) -> None:
        """Reload if file has changed."""
        if not self._filepath.exists():
            return
        
        current_mtime = self._filepath.stat().st_mtime
        if current_mtime > self._last_mtime:
            logger.info(f"Detected change in {self._filepath}, reloading...")
            await self.load()
            await self._notify_listeners()
    
    def check_for_changes(self) -> bool:
        """Check if file has been modified."""
        if not self._filepath.exists():
            return False
        return self._filepath.stat().st_mtime > self._last_mtime


class PostgreSQLDataSource(DataSource):
    """Load customer data from PostgreSQL.
    
    Requires asyncpg: pip install asyncpg
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "icda",
        user: str = "postgres",
        password: str = "",
        table: str = "customers",
    ):
        super().__init__()
        self._host = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._table = table
        self._pool = None
    
    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            try:
                import asyncpg
                self._pool = await asyncpg.create_pool(
                    host=self._host,
                    port=self._port,
                    database=self._database,
                    user=self._user,
                    password=self._password,
                    min_size=1,
                    max_size=10,
                )
            except ImportError:
                logger.error("asyncpg not installed. Run: pip install asyncpg")
                raise
        return self._pool
    
    async def load(self) -> None:
        """Load all customers from PostgreSQL."""
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(f"SELECT * FROM {self._table}")
                self._customers = [dict(row) for row in rows]
            
            self._build_indexes()
            self._metadata = self._build_metadata()
            self._metadata.source_type = "postgresql"
            self._metadata.source_uri = f"postgresql://{self._host}:{self._port}/{self._database}"
            
            logger.info(f"Loaded {len(self._customers)} customers from PostgreSQL")
            
        except Exception as e:
            logger.error(f"Failed to load from PostgreSQL: {e}")
            self._customers = []
            self._metadata = self._build_metadata()
    
    async def reload(self) -> None:
        """Reload data from PostgreSQL."""
        await self.load()
        await self._notify_listeners()
    
    async def close(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()


class MongoDBDataSource(DataSource):
    """Load customer data from MongoDB.
    
    Requires motor: pip install motor
    """
    
    def __init__(
        self,
        uri: str = "mongodb://localhost:27017",
        database: str = "icda",
        collection: str = "customers",
    ):
        super().__init__()
        self._uri = uri
        self._database = database
        self._collection = collection
        self._client = None
    
    async def _get_client(self):
        """Get or create MongoDB client."""
        if self._client is None:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                self._client = AsyncIOMotorClient(self._uri)
            except ImportError:
                logger.error("motor not installed. Run: pip install motor")
                raise
        return self._client
    
    async def load(self) -> None:
        """Load all customers from MongoDB."""
        try:
            client = await self._get_client()
            db = client[self._database]
            collection = db[self._collection]
            
            cursor = collection.find({})
            self._customers = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
                self._customers.append(doc)
            
            self._build_indexes()
            self._metadata = self._build_metadata()
            self._metadata.source_type = "mongodb"
            self._metadata.source_uri = f"{self._uri}/{self._database}.{self._collection}"
            
            logger.info(f"Loaded {len(self._customers)} customers from MongoDB")
            
        except Exception as e:
            logger.error(f"Failed to load from MongoDB: {e}")
            self._customers = []
            self._metadata = self._build_metadata()
    
    async def reload(self) -> None:
        """Reload data from MongoDB."""
        await self.load()
        await self._notify_listeners()
    
    async def close(self) -> None:
        """Close MongoDB client."""
        if self._client:
            self._client.close()


class CSVDataSource(DataSource):
    """Load customer data from CSV file."""
    
    def __init__(self, filepath: Path | str, encoding: str = "utf-8"):
        super().__init__()
        self._filepath = Path(filepath)
        self._encoding = encoding
        self._last_mtime: float = 0
    
    async def load(self) -> None:
        """Load data from CSV file."""
        import csv
        
        if not self._filepath.exists():
            logger.warning(f"CSV file not found: {self._filepath}")
            self._customers = []
            self._metadata = self._build_metadata()
            return
        
        try:
            with open(self._filepath, "r", encoding=self._encoding) as f:
                reader = csv.DictReader(f)
                self._customers = list(reader)
            
            # Convert numeric fields
            for c in self._customers:
                if "move_count" in c:
                    try:
                        c["move_count"] = int(c["move_count"])
                    except (ValueError, TypeError):
                        c["move_count"] = 0
            
            self._last_mtime = self._filepath.stat().st_mtime
            self._build_indexes()
            self._metadata = self._build_metadata()
            self._metadata.source_type = "csv_file"
            self._metadata.source_uri = str(self._filepath)
            
            logger.info(f"Loaded {len(self._customers)} customers from CSV")
            
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            self._customers = []
            self._metadata = self._build_metadata()
    
    async def reload(self) -> None:
        """Reload if file changed."""
        if self._filepath.exists():
            current_mtime = self._filepath.stat().st_mtime
            if current_mtime > self._last_mtime:
                await self.load()
                await self._notify_listeners()


def create_data_source(config: dict[str, Any]) -> DataSource:
    """Factory function to create appropriate data source from config.
    
    Config examples:
        {"type": "json", "path": "/data/customers.json"}
        {"type": "postgresql", "host": "localhost", "database": "icda"}
        {"type": "mongodb", "uri": "mongodb://localhost:27017", "database": "icda"}
        {"type": "csv", "path": "/data/customers.csv"}
    """
    source_type = config.get("type", "json").lower()
    
    match source_type:
        case "json":
            return JSONFileDataSource(config.get("path", "customer_data.json"))
        case "postgresql" | "postgres" | "pg":
            return PostgreSQLDataSource(
                host=config.get("host", "localhost"),
                port=config.get("port", 5432),
                database=config.get("database", "icda"),
                user=config.get("user", "postgres"),
                password=config.get("password", ""),
                table=config.get("table", "customers"),
            )
        case "mongodb" | "mongo":
            return MongoDBDataSource(
                uri=config.get("uri", "mongodb://localhost:27017"),
                database=config.get("database", "icda"),
                collection=config.get("collection", "customers"),
            )
        case "csv":
            return CSVDataSource(
                filepath=config.get("path", "customers.csv"),
                encoding=config.get("encoding", "utf-8"),
            )
        case _:
            raise ValueError(f"Unknown data source type: {source_type}")
