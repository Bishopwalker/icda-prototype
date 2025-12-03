import boto3
from botocore.exceptions import ClientError

from .database import CustomerDB


class NovaClient:
    __slots__ = ("client", "model", "available", "db")

    _PROMPT = "You are ICDA, an AI assistant for customer data queries. Be concise. Never provide SSN, financial, or health info."

    TOOLS = [
        {"toolSpec": {"name": "lookup_crid", "description": "Look up customer by CRID",
            "inputSchema": {"json": {"type": "object", "properties": {"crid": {"type": "string"}}, "required": ["crid"]}}}},
        {"toolSpec": {"name": "search_customers", "description": "Search customers by state, city, or move count",
            "inputSchema": {"json": {"type": "object", "properties": {
                "state": {"type": "string"}, "city": {"type": "string"},
                "min_move_count": {"type": "integer"}, "limit": {"type": "integer"}}}}}},
        {"toolSpec": {"name": "get_stats", "description": "Get customer statistics",
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
            inferenceConfig={"maxTokens": 1024, "temperature": 0.1}
        )

    async def query(self, text: str) -> dict:
        if not self.available:
            return {"success": False, "error": "Nova not available"}
        try:
            resp = self._converse([{"role": "user", "content": [{"text": text}]}])
            content = resp["output"]["message"]["content"]

            if tool := next((b["toolUse"] for b in content if "toolUse" in b), None):
                result = self._execute_tool(tool["name"], tool["input"])
                follow = self._converse([
                    {"role": "user", "content": [{"text": text}]},
                    {"role": "assistant", "content": content},
                    {"role": "user", "content": [{"toolResult": {"toolUseId": tool["toolUseId"], "content": [{"json": result}]}}]}
                ])
                if out := next((b["text"] for b in follow["output"]["message"]["content"] if "text" in b), None):
                    return {"success": True, "response": out, "tool": tool["name"]}

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
                    min_moves=params.get("min_move_count"), limit=params.get("limit", 10)
                )
            case "get_stats":
                return self.db.stats()
        return {"success": False, "error": f"Unknown tool: {name}"}
