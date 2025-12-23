"""Pytest configuration and shared fixtures."""

import pytest
import pytest_asyncio
import sys
import json
import uuid
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Configure pytest-asyncio
def pytest_configure(config):
    """Configure pytest-asyncio settings."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )


# ============================================================================
# Event Loop Configuration
# ============================================================================


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy for Windows compatibility."""
    import asyncio
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.get_event_loop_policy()


# ============================================================================
# E2E Test Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def api_base_url() -> str:
    """Base URL for API requests."""
    return "http://localhost:8000"


@pytest_asyncio.fixture
async def live_api_client(api_base_url: str):
    """
    Async HTTP client for live API testing.

    Requires:
    - Backend running on port 8000
    - Docker infrastructure (Redis, OpenSearch) running
    """
    import httpx

    try:
        async with httpx.AsyncClient(
            base_url=api_base_url,
            timeout=60.0,  # Long timeout for Nova calls
        ) as client:
            # Verify API is accessible
            try:
                response = await client.get("/api/health")
                if response.status_code != 200:
                    pytest.skip(f"API not healthy: {response.status_code}")
            except httpx.ConnectError:
                pytest.skip("API not running on localhost:8000 - start with: uvicorn main:app --port 8000")
            except httpx.ReadTimeout:
                pytest.skip("API timeout - server may be starting up")

            yield client
    except httpx.ConnectError:
        pytest.skip("Cannot connect to API at localhost:8000")
    except Exception as e:
        pytest.skip(f"API connection failed: {e}")


@pytest.fixture
def session_id() -> str:
    """Generate unique session ID for conversation tests."""
    return str(uuid.uuid4())


@pytest.fixture
def corrupted_addresses() -> list[dict]:
    """Load pre-generated corrupted addresses for batch testing."""
    fixture_path = project_root / "tests" / "fixtures" / "corrupted_addresses.json"
    if not fixture_path.exists():
        pytest.skip(f"Fixture not found: {fixture_path}")

    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def sample_corrupted_addresses(corrupted_addresses: list[dict]) -> list[dict]:
    """Subset of corrupted addresses for faster testing."""
    return corrupted_addresses[:20]


@pytest.fixture
def guardrails_off() -> dict:
    """Guardrails configuration with all protections disabled."""
    return {
        "pii": False,
        "financial": False,
        "credentials": False,
        "offtopic": False,
    }


@pytest.fixture
def guardrails_on() -> dict:
    """Guardrails configuration with all protections enabled (default)."""
    return {
        "pii": True,
        "financial": True,
        "credentials": True,
        "offtopic": True,
    }


@pytest.fixture
def customer_data() -> list[dict]:
    """Load customer data for reference in tests."""
    data_path = project_root / "customer_data.json"
    if not data_path.exists():
        pytest.skip(f"Customer data not found: {data_path}")

    with open(data_path) as f:
        return json.load(f)
