import boto3
from botocore.exceptions import ClientError

from .database import CustomerDB


class NovaClient:
    __slots__ = ("client", "model", "available", "db")

    _PROMPT = """You are ICDA, a customer data assistant. Be concise and helpful.

QUERY INTERPRETATION:
- Interpret queries flexibly, not literally
- State names → abbreviations (Nevada=NV, California=CA, Texas=TX)
- "high movers"/"frequent movers" → min_move_count 3+
- Use reasonable defaults (limit=10 for searches)
- Never provide SSN, financial, or health info
- Use conversation history for context"""

    TOOLS = [
        {"toolSpec": {"name": "lookup_crid", "description": "Look up a specific customer by their CRID (Customer Record ID). Use when user mentions a specific CRID or customer ID.",
            "inputSchema": {"json": {"type": "object", "properties": {"crid": {"type": "string", "description": "The Customer Record ID (e.g., CRID-00001)"}}, "required": ["crid"]}}}},
        {"toolSpec": {"name": "search_customers", "description": "Search for customers with flexible filters. Use when user asks about customers in a state/city, customers who moved, or general customer searches. Interpret informal language: 'Nevada folks'=state NV, 'high movers'=min_move_count 3+, 'California customers'=state CA.",
            "inputSchema": {"json": {"type": "object", "properties": {
                "state": {"type": "string", "description": "Two-letter state code (NV, CA, TX, NY, FL, etc). Convert state names to codes."},
                "city": {"type": "string", "description": "City name to filter by"},
                "min_move_count": {"type": "integer", "description": "Minimum number of moves. Use 2-3 for 'frequent movers', 5+ for 'high movers'"},
                "limit": {"type": "integer", "description": "Max results to return (default 10, max 100)"}}}}}},
        {"toolSpec": {"name": "get_stats", "description": "Get overall customer statistics including counts by state. Use for questions like 'how many customers', 'totals', 'breakdown', or any aggregate data questions.",
            "inputSchema": {"json": {"type": "object", "properties": {}}}}}
    ]

    def __init__(self, region: str, model: str, db: CustomerDB):
        self.model = model
        self.db = db
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
        except Exception as e:
            print(f"Nova init failed: {e}")
            self.available = False

    def _converse(self, messages: list) -> dict:
        return self.client.converse(
            modelId=self.model,
            messages=messages,
            system=[{"text": self._PROMPT}],
            toolConfig={"tools": self.TOOLS, "toolChoice": {"auto": {}}},
            inferenceConfig={"maxTokens": 4096, "temperature": 0.1}
        )

    async def query(self, text: str, history: list[dict] | None = None) -> dict:
        """
        Query Nova with optional conversation history.

        Args:
            text: The user's query
            history: Previous messages in Bedrock format [{"role": "user/assistant", "content": [{"text": "..."}]}]
                     IMPORTANT: History must only contain text content, not toolUse blocks!

        Returns:
            dict with success, response, and optional tool used
        """
        if not self.available:
            return {"success": False, "error": "Nova not available"}

        try:
            # Build messages: history + current query
            # Filter history to ensure only text content (no toolUse blocks that would require toolResult)
            messages = []
            if history:
                for msg in history:
                    # Only include messages with pure text content
                    clean_content = [b for b in msg.get("content", []) if "text" in b]
                    if clean_content:
                        messages.append({"role": msg["role"], "content": clean_content})
            messages.append({"role": "user", "content": [{"text": text}]})

            resp = self._converse(messages)
            content = resp["output"]["message"]["content"]

            # Handle ALL tool calls in the response
            tools = [b["toolUse"] for b in content if "toolUse" in b]
            if tools:
                # Execute all tools and collect results
                tool_results = []
                tool_names = []
                for tool in tools:
                    result = self._execute_tool(tool["name"], tool["input"])
                    tool_results.append({
                        "toolResult": {
                            "toolUseId": tool["toolUseId"],
                            "content": [{"json": result}]
                        }
                    })
                    tool_names.append(tool["name"])

                # Continue with ALL tool results
                follow_messages = messages + [
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": tool_results}
                ]
                follow = self._converse(follow_messages)

                if out := next((b["text"] for b in follow["output"]["message"]["content"] if "text" in b), None):
                    return {"success": True, "response": out, "tool": ", ".join(tool_names)}

            if out := next((b["text"] for b in content if "text" in b), None):
                return {"success": True, "response": out}
            return {"success": False, "error": "No response"}

        except ClientError as e:
            return {"success": False, "error": f"Nova: {e.response['Error']['Message']}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_tool(self, name: str, params: dict) -> dict:
        match name:
            case "lookup_crid":
                return self.db.lookup(params.get("crid", ""))
            case "search_customers":
                return self.db.search(
                    state=params.get("state"), city=params.get("city"),
                    min_moves=params.get("min_move_count"), limit=params.get("limit")
                )
            case "get_stats":
                return self.db.stats()
        return {"success": False, "error": f"Unknown tool: {name}"}