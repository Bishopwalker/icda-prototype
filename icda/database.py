import json
import re
from pathlib import Path
from bisect import bisect_left


class CustomerDB:
    __slots__ = ("customers", "by_crid", "by_state", "address_index", "name_index", "city_index", "available_states")

    STATE_NAMES = {"NV": "nevada", "CA": "california", "TX": "texas", "AZ": "arizona", "FL": "florida",
                   "NY": "new york", "WA": "washington", "CO": "colorado", "VA": "virginia",
                   "GA": "georgia", "NC": "north carolina", "IL": "illinois", "PA": "pennsylvania",
                   "OH": "ohio", "MI": "michigan"}

    # Full state name to code mapping for parsing user queries
    STATE_NAME_TO_CODE = {
        "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
        "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
        "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
        "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
        "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
        "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
        "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
        "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
        "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
        "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI",
        "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX",
        "utah": "UT", "vermont": "VT", "virginia": "VA", "washington": "WA",
        "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    }

    # Reverse mapping: code to full name
    STATE_CODE_TO_NAME = {v: k.title() for k, v in STATE_NAME_TO_CODE.items()}

    def __init__(self, data_file: Path):
        self.customers = self._load(data_file)
        self.by_crid = {c["crid"]: c for c in self.customers}
        self.by_state: dict[str, list] = {}
        for c in self.customers:
            self.by_state.setdefault(c["state"], []).append(c)
        # Track which states actually have data
        self.available_states = set(self.by_state.keys())
        print(f"Available states in dataset: {sorted(self.available_states)}")
        # Build autocomplete indexes
        self._build_autocomplete_indexes()

    def _load(self, path: Path) -> list[dict]:
        if path.exists():
            data = json.loads(path.read_text())
            print(f"Loaded {len(data)} customers")
            return data
        print(f"{path} not found")
        return []

    def _build_autocomplete_indexes(self):
        """Build sorted indexes for fast prefix-based autocomplete"""
        # Address index: (lowercase_address, customer)
        self.address_index = sorted(
            [(c["address"].lower(), c) for c in self.customers],
            key=lambda x: x[0]
        )
        # Name index: (lowercase_name, customer)
        self.name_index = sorted(
            [(c["name"].lower(), c) for c in self.customers],
            key=lambda x: x[0]
        )
        # City index: (lowercase_city, customer)
        self.city_index = sorted(
            [(c["city"].lower(), c) for c in self.customers],
            key=lambda x: x[0]
        )
        print(f"Built autocomplete indexes for {len(self.customers)} customers")

    def has_state(self, state_code: str) -> bool:
        """Check if a state exists in the dataset."""
        return state_code.upper() in self.available_states

    def get_available_states(self) -> list[str]:
        """Get list of states with data, sorted by customer count descending."""
        return sorted(self.available_states, key=lambda s: len(self.by_state.get(s, [])), reverse=True)

    def get_state_counts(self) -> dict[str, int]:
        """Get customer count per state."""
        return {s: len(customers) for s, customers in self.by_state.items()}

    def parse_state_from_query(self, query: str) -> tuple[str | None, str | None]:
        """Parse state from query, return (state_code, state_name) or (None, None).
        
        Also detects if user asked for a state not in the dataset.
        """
        q = query.lower()
        
        # Check for full state names first
        for name, code in self.STATE_NAME_TO_CODE.items():
            if name in q:
                return (code, name.title())
        
        # Check for state codes
        state_match = re.search(r'\b([A-Z]{2})\b', query.upper())
        if state_match:
            code = state_match.group(1)
            name = self.STATE_CODE_TO_NAME.get(code)
            if name:
                return (code, name)
        
        return (None, None)

    def autocomplete(self, field: str, prefix: str, limit: int = 10) -> dict:
        """
        Fast prefix-based autocomplete using binary search.
        field: 'address', 'name', or 'city'
        prefix: the text to match
        limit: max results to return
        """
        prefix_lower = prefix.lower().strip()
        if not prefix_lower:
            return {"success": False, "error": "Empty prefix"}

        # Select the appropriate index
        index = {
            "address": self.address_index,
            "name": self.name_index,
            "city": self.city_index
        }.get(field)

        if not index:
            return {"success": False, "error": f"Unknown field: {field}. Use 'address', 'name', or 'city'"}

        # Binary search for the start position
        pos = bisect_left(index, (prefix_lower,))

        # Collect matches
        results = []
        seen_values = set()  # For deduplication (e.g., same city name)

        while pos < len(index) and len(results) < limit:
            value, customer = index[pos]
            if not value.startswith(prefix_lower):
                break

            # For city autocomplete, deduplicate
            if field == "city":
                city_key = customer["city"].lower()
                if city_key not in seen_values:
                    seen_values.add(city_key)
                    results.append({
                        "value": customer["city"],
                        "state": customer["state"],
                        "count": sum(1 for c in self.customers if c["city"].lower() == city_key)
                    })
            else:
                results.append({
                    "crid": customer["crid"],
                    "value": customer[field],
                    "name": customer["name"],
                    "city": customer["city"],
                    "state": customer["state"]
                })
            pos += 1

        return {"success": True, "field": field, "prefix": prefix, "count": len(results), "data": results}

    def autocomplete_fuzzy(self, field: str, query: str, limit: int = 10) -> dict:
        """
        Fuzzy autocomplete using trigram-like similarity.
        Slower but handles typos and partial matches.
        """
        query_lower = query.lower().strip()
        if len(query_lower) < 2:
            return {"success": False, "error": "Query too short (min 2 chars)"}

        # Select field to search
        if field not in ("address", "name", "city"):
            return {"success": False, "error": f"Unknown field: {field}"}

        # Score each customer by similarity
        def similarity(text: str) -> float:
            text_lower = text.lower()
            # Exact prefix match = highest score
            if text_lower.startswith(query_lower):
                return 1.0 + len(query_lower) / len(text_lower)
            # Contains match
            if query_lower in text_lower:
                return 0.8
            # Word starts with query
            words = text_lower.split()
            if any(w.startswith(query_lower) for w in words):
                return 0.7
            # Character overlap (trigram-like)
            query_chars = set(query_lower)
            text_chars = set(text_lower)
            overlap = len(query_chars & text_chars) / len(query_chars)
            return overlap * 0.5 if overlap > 0.6 else 0

        scored = []
        seen = set()
        for c in self.customers:
            value = c[field]
            score = similarity(value)
            if score > 0.4 and value.lower() not in seen:
                seen.add(value.lower())
                scored.append((score, c))

        # Sort by score descending, take top results
        scored.sort(key=lambda x: -x[0])
        results = [
            {"crid": c["crid"], "value": c[field], "name": c["name"],
             "city": c["city"], "state": c["state"], "score": round(s, 2)}
            for s, c in scored[:limit]
        ]

        return {"success": True, "field": field, "query": query, "count": len(results), "data": results}

    def lookup(self, crid: str) -> dict:
        crid = crid.upper()
        if crid.startswith("CRID-"):
            num = crid.removeprefix("CRID-")
            for fmt in (f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(3)}", crid):
                if data := self.by_crid.get(fmt):
                    return {"success": True, "data": data}
        return {"success": False, "error": f"CRID {crid} not found"}

    def search(self, state: str = None, city: str = None, min_moves: int = None, customer_type: str = None, has_apartment: bool = None, limit: int = None) -> dict:
        """Search customers with filters. Returns error if requested state not in dataset."""
        
        # Check if requested state exists in dataset
        if state:
            state_upper = state.upper()
            if state_upper not in self.available_states:
                # State was requested but doesn't exist in our data
                available = self.get_available_states()
                state_name = self.STATE_CODE_TO_NAME.get(state_upper, state_upper)
                return {
                    "success": False,
                    "error": "state_not_available",
                    "message": f"No customer data available for {state_name} ({state_upper}).",
                    "requested_state": state_upper,
                    "requested_state_name": state_name,
                    "available_states": available,
                    "available_states_with_counts": {s: len(self.by_state[s]) for s in available},
                    "suggestion": f"Try one of our available states: {', '.join(available[:5])}...",
                }
            results = self.by_state.get(state_upper, [])
        else:
            results = self.customers
            
        if min_moves:
            results = [c for c in results if c["move_count"] >= min_moves]
        if city:
            city_lower = city.casefold()
            results = [c for c in results if city_lower in c["city"].casefold()]
        if customer_type:
            ct_upper = customer_type.upper()
            results = [c for c in results if c.get("customer_type", "").upper() == ct_upper]
        if has_apartment:
            # Filter for addresses containing "Apt" or "Unit" (apartment/unit renters)
            results = [c for c in results if "apt" in c.get("address", "").lower() or "unit" in c.get("address", "").lower()]
        data = results[:limit] if limit else results
        return {"success": True, "total": len(results), "data": data}

    def stats(self) -> dict:
        return {"success": True, "data": {s: len(c) for s, c in self.by_state.items()}, "total": len(self.customers)}

    def execute(self, tool: str, query: str) -> dict:
        q = query.casefold()
        match tool:
            case "lookup_crid":
                if m := re.search(r"crid[-:\s]*(\d+)", q):
                    return self.lookup(f"CRID-{m.group(1)}")
                return {"success": False, "error": "No CRID found in query"}
            case "search_customers":
                # Parse state from query - check if it exists
                state_code, state_name = self.parse_state_from_query(query)
                if state_code and state_code not in self.available_states:
                    # User asked for a state we don't have
                    available = self.get_available_states()
                    return {
                        "success": False,
                        "error": "state_not_available",
                        "message": f"No customer data available for {state_name} ({state_code}).",
                        "requested_state": state_code,
                        "requested_state_name": state_name,
                        "available_states": available,
                        "available_states_with_counts": {s: len(self.by_state[s]) for s in available},
                        "suggestion": f"Try one of our available states: {', '.join(available[:5])}...",
                    }
                
                # Original logic for states we do have
                state = next((s for s in self.by_state if s.lower() in q or self.STATE_NAMES.get(s, "").lower() in q), None)
                min_moves = int(m.group(1)) if (m := re.search(r"(\d+)\+?\s*(?:times|moves)", q)) else None
                if "twice" in q: min_moves = 2
                if "three" in q: min_moves = 3
                return self.search(state=state, min_moves=min_moves)
            case "get_stats":
                return self.stats()
        return {"success": False, "error": f"Unknown tool: {tool}"}
