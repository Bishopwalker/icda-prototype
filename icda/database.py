import json
import re
from pathlib import Path


class CustomerDB:
    __slots__ = ("customers", "by_crid", "by_state")

    STATE_NAMES = {"NV": "nevada", "CA": "california", "TX": "texas", "AZ": "arizona", "FL": "florida"}

    def __init__(self, data_file: Path):
        self.customers = self._load(data_file)
        self.by_crid = {c["crid"]: c for c in self.customers}
        self.by_state: dict[str, list] = {}
        for c in self.customers:
            self.by_state.setdefault(c["state"], []).append(c)

    def _load(self, path: Path) -> list[dict]:
        if path.exists():
            data = json.loads(path.read_text())
            print(f"Loaded {len(data)} customers")
            return data
        print(f"{path} not found")
        return []

    def lookup(self, crid: str) -> dict:
        crid = crid.upper()
        if crid.startswith("CRID-"):
            num = crid.removeprefix("CRID-")
            for fmt in (f"CRID-{num.zfill(6)}", f"CRID-{num.zfill(3)}", crid):
                if data := self.by_crid.get(fmt):
                    return {"success": True, "data": data}
        return {"success": False, "error": f"CRID {crid} not found"}

    def search(self, state: str = None, city: str = None, min_moves: int = None, limit: int = 10) -> dict:
        results = self.by_state.get(state.upper(), []) if state else self.customers
        if min_moves:
            results = [c for c in results if c["move_count"] >= min_moves]
        if city:
            city_lower = city.casefold()
            results = [c for c in results if city_lower in c["city"].casefold()]
        return {"success": True, "total": len(results), "data": results[:min(limit, 100)]}

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
                state = next((s for s in self.by_state if s.lower() in q or self.STATE_NAMES.get(s, "").lower() in q), None)
                min_moves = int(m.group(1)) if (m := re.search(r"(\d+)\+?\s*(?:times|moves)", q)) else None
                if "twice" in q: min_moves = 2
                if "three" in q: min_moves = 3
                return self.search(state=state, min_moves=min_moves)
            case "get_stats":
                return self.stats()
        return {"success": False, "error": f"Unknown tool: {tool}"}
