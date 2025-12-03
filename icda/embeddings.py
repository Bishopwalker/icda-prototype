import json
import boto3


class EmbeddingClient:
    __slots__ = ("client", "model", "dimensions", "available")

    def __init__(self, region: str, model: str, dimensions: int = 1024):
        self.model = model
        self.dimensions = dimensions
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
        except Exception as e:
            print(f"Embedding client init failed: {e}")
            self.available = False

    def embed(self, text: str) -> list[float]:
        if not self.available:
            return []
        resp = self.client.invoke_model(
            modelId=self.model,
            body=json.dumps({"inputText": text, "dimensions": self.dimensions, "normalize": True})
        )
        return json.loads(resp["body"].read())["embedding"]
