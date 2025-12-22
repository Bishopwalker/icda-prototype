import json
import os

import boto3
from botocore.exceptions import NoCredentialsError, ClientError


class EmbeddingClient:
    """
    Titan Embedding client for Bedrock.
    Gracefully handles missing AWS credentials.
    """
    __slots__ = ("client", "model", "dimensions", "available")

    def __init__(self, region: str, model: str, dimensions: int = 1024):
        self.model = model
        self.dimensions = dimensions
        self.client = None
        self.available = False

        # Try to connect using boto3's default credential chain
        # This supports: env vars, AWS profile, IAM role, SSO, instance profile, etc.
        try:
            self.client = boto3.client("bedrock-runtime", region_name=region)
            # Verify we have valid credentials by checking session
            session = boto3.Session()
            creds = session.get_credentials()
            if creds is None:
                print("Embeddings: No AWS credentials found - running in LITE MODE (no semantic search)")
                return
            self.available = True
            print(f"Embeddings: Titan connected ({model})")
        except NoCredentialsError:
            print("Embeddings: AWS credentials not found - running in LITE MODE")
        except Exception as e:
            print(f"Embeddings: Init failed - {e}")

    def embed(self, text: str) -> list[float]:
        """Generate embedding vector for text. Returns empty list if unavailable."""
        if not self.available or not self.client:
            return []

        try:
            resp = self.client.invoke_model(
                modelId=self.model,
                body=json.dumps({
                    "inputText": text,
                    "dimensions": self.dimensions,
                    "normalize": True
                })
            )
            return json.loads(resp["body"].read())["embedding"]
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("AccessDeniedException", "UnrecognizedClientException"):
                print(f"Embeddings: AWS access denied - check IAM permissions")
                self.available = False
            return []
        except Exception as e:
            print(f"Embeddings: Error - {e}")
            return []
