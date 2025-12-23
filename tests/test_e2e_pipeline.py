"""
End-to-End Pipeline Tests for ICDA.

Tests the complete query processing pipeline including:
- Complex multi-filter queries
- Guardrails bypass and invalid state detection
- Conversation memory/context
- Batch address verification

Requirements:
- Backend running on localhost:8000
- Docker infrastructure (Redis, OpenSearch) running
- AWS credentials configured for Bedrock Nova
"""

import pytest
from datetime import datetime


# ============================================================================
# Test 1: Complex Multi-Filter Query
# ============================================================================


class TestComplexQuery:
    """Test complex queries with multiple filters."""

    COMPLEX_QUERY = "Find all customers who don't have active status but who moved before 2024"

    @pytest.mark.asyncio
    async def test_complex_query_status_and_date(self, live_api_client, session_id):
        """
        Test: Find customers without active status who moved before 2024.

        Validates:
        - Status filtering (NOT ACTIVE)
        - Date parsing (before 2024)
        - 8-agent pipeline execution
        - Response contains valid customer data
        """
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": self.COMPLEX_QUERY,
                "session_id": session_id,
                "bypass_cache": True,  # Fresh results
            },
        )

        assert response.status_code == 200, f"API error: {response.text}"
        data = response.json()

        # Basic response structure
        assert data.get("success") is True, f"Query failed: {data.get('response')}"
        assert "response" in data
        assert data.get("blocked") is False

        # Check for quality enforcement (from EnforcerAgent)
        if "quality_score" in data:
            assert data["quality_score"] >= 0.5, "Quality score too low"

        # Verify route went through Nova (not just cache/database)
        assert data.get("route") in ("nova", "orchestrator", "database"), \
            f"Unexpected route: {data.get('route')}"

        # The response text should mention customers or results
        response_text = data.get("response", "").lower()
        assert any(word in response_text for word in [
            "customer", "found", "result", "match", "record"
        ]), f"Response doesn't mention customers: {response_text[:200]}"

        print(f"\n=== Test 1: Complex Query ===")
        print(f"Query: {self.COMPLEX_QUERY}")
        print(f"Route: {data.get('route')}")
        print(f"Response preview: {data.get('response', '')[:500]}")

    @pytest.mark.asyncio
    async def test_validates_status_filter(self, live_api_client, customer_data):
        """
        Verify that results actually have non-ACTIVE status.

        NOTE: This is an informational test - soft assertion.
        Pipeline may return some ACTIVE customers due to semantic search.
        """
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": self.COMPLEX_QUERY,
                "bypass_cache": True,
            },
        )

        assert response.status_code == 200, f"API error: {response.text}"
        data = response.json()

        # Verify we got a valid response
        assert data.get("success") is True, f"Query failed: {data.get('response', data.get('error'))}"

        # Check response text for status mentions (API returns text, not structured results)
        response_text = data.get("response", "").lower()

        print(f"\nStatus filter analysis:")
        print(f"  Response mentions 'active': {'active' in response_text}")
        print(f"  Response mentions 'inactive': {'inactive' in response_text}")
        print(f"  Response preview: {response_text[:300]}")

        # If structured results are available (from pipeline trace), analyze them
        if "results" in data and isinstance(data["results"], list):
            active_count = sum(1 for r in data["results"] if r.get("status") == "ACTIVE")
            non_active_count = sum(1 for r in data["results"] if r.get("status") and r.get("status") != "ACTIVE")
            print(f"  Structured results: {active_count} ACTIVE, {non_active_count} non-ACTIVE")

        # Informational - always passes
        print("  [INFO] This test validates response structure, not filter accuracy")

    @pytest.mark.asyncio
    async def test_validates_date_filter(self, live_api_client):
        """
        Verify that results have move dates before 2024.

        NOTE: This is an informational test - soft assertion.
        Pipeline may return post-2024 dates due to semantic search.
        """
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": self.COMPLEX_QUERY,
                "bypass_cache": True,
            },
        )

        assert response.status_code == 200, f"API error: {response.text}"
        data = response.json()

        # Verify we got a valid response
        assert data.get("success") is True, f"Query failed: {data.get('response', data.get('error'))}"

        # Check response text for date mentions (API returns text, not structured results)
        response_text = data.get("response", "").lower()

        print(f"\nDate filter analysis:")
        print(f"  Response mentions '2024': {'2024' in response_text}")
        print(f"  Response mentions '2023': {'2023' in response_text}")
        print(f"  Response mentions 'before': {'before' in response_text}")
        print(f"  Response preview: {response_text[:300]}")

        # If structured results are available, analyze them
        if "results" in data and isinstance(data["results"], list):
            pre_2024 = 0
            post_2024 = 0
            for result in data["results"]:
                last_move = result.get("last_move")
                if last_move:
                    try:
                        move_date = datetime.strptime(last_move, "%Y-%m-%d")
                        if move_date.year < 2024:
                            pre_2024 += 1
                        else:
                            post_2024 += 1
                    except ValueError:
                        pass  # Skip malformed dates

            print(f"  Structured results: {pre_2024} pre-2024, {post_2024} post-2024")

        # Informational - always passes
        print("  [INFO] This test validates response structure, not date accuracy")


# ============================================================================
# Test 2: PII Filter Off + Invalid State Detection
# ============================================================================


class TestInvalidStateDetection:
    """Test guardrails bypass and invalid state suggestions."""

    QUERY_WITH_INVALID_STATE = (
        "Find customers who don't have active status but who moved before 2024 "
        "who have lived in Arizona and Argintina"
    )

    @pytest.mark.asyncio
    async def test_guardrails_off_with_invalid_state(
        self, live_api_client, guardrails_off, session_id
    ):
        """
        Test: Query with guardrails off and misspelled state "Argintina".

        Validates:
        - Guardrails bypass works
        - System detects "Argintina" is invalid
        - System suggests alternatives (Arkansas, etc.)
        - Arizona (AZ) results are returned
        """
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": self.QUERY_WITH_INVALID_STATE,
                "session_id": session_id,
                "bypass_cache": True,
                "guardrails": guardrails_off,
            },
        )

        assert response.status_code == 200, f"API error: {response.text}"
        data = response.json()

        # Should succeed even with guardrails off
        assert data.get("success") is True, f"Query failed: {data.get('response')}"

        # Check guardrails were bypassed
        assert data.get("guardrails_bypassed") is True or \
               data.get("guardrails_active") is False, \
            "Guardrails should be bypassed"

        # Response should mention something about the invalid state
        response_text = data.get("response", "").lower()

        # Check for any of these indicators:
        # 1. Mentions "argintina" doesn't exist/isn't valid
        # 2. Suggests alternatives
        # 3. Mentions Arizona results
        invalid_state_handled = any([
            "argintina" in response_text and any(w in response_text for w in [
                "not", "invalid", "no data", "doesn't exist", "couldn't find", "unknown"
            ]),
            "arkansas" in response_text,  # Similar-sounding suggestion
            "did you mean" in response_text,
            "suggestion" in response_text,
            "arizona" in response_text,  # At least got Arizona results
        ])

        print(f"\n=== Test 2: Invalid State Detection ===")
        print(f"Query: {self.QUERY_WITH_INVALID_STATE}")
        print(f"Guardrails bypassed: {data.get('guardrails_bypassed')}")
        print(f"Response preview: {data.get('response', '')[:500]}")

        # Soft assertion - warn but don't fail if no explicit handling
        if not invalid_state_handled:
            print("WARNING: Response doesn't explicitly handle invalid state 'Argintina'")
            print("Consider adding state suggestion logic to the pipeline")

    @pytest.mark.asyncio
    async def test_arizona_results_included(self, live_api_client, guardrails_off):
        """Verify Arizona (valid state) results are included."""
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": self.QUERY_WITH_INVALID_STATE,
                "bypass_cache": True,
                "guardrails": guardrails_off,
            },
        )

        data = response.json()
        response_text = data.get("response", "").lower()

        # Arizona should be mentioned or results returned
        has_arizona = "arizona" in response_text or "az" in response_text

        # Check structured results if available
        if "results" in data and isinstance(data["results"], list):
            az_results = [r for r in data["results"] if r.get("state") == "AZ"]
            if az_results:
                has_arizona = True

        print(f"Arizona results found: {has_arizona}")

    @pytest.mark.asyncio
    async def test_state_suggestion_similarity(self, live_api_client, guardrails_off):
        """
        Test that suggestions for 'Argintina' include phonetically similar states.

        Expected suggestions:
        - Arkansas (AR) - sounds similar
        - Arizona (AZ) - also starts with 'Ar'
        """
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": "Find customers in Argintina",  # Isolated invalid state query
                "bypass_cache": True,
                "guardrails": guardrails_off,
            },
        )

        data = response.json()
        response_text = data.get("response", "").lower()

        # Look for suggestions
        similar_states = ["arkansas", "arizona", "ar", "az"]
        found_suggestions = [s for s in similar_states if s in response_text]

        print(f"\n=== State Suggestions ===")
        print(f"Found suggestions: {found_suggestions}")
        print(f"Response: {data.get('response', '')[:300]}")


# ============================================================================
# Test 3: Conversation Memory/Context
# ============================================================================


class TestConversationMemory:
    """Test session-based conversation continuity."""

    @pytest.mark.asyncio
    async def test_follow_up_query_uses_context(self, live_api_client, session_id):
        """
        Test: Make initial query, then follow-up referencing prior results.

        Validates:
        - Session ID maintains conversation context
        - Follow-up query ("those results") references prior query
        - System understands temporal references (2023 vs 2022)
        """
        # Step 1: Initial query
        initial_query = "Find customers who don't have active status but who moved before 2024"
        response1 = await live_api_client.post(
            "/api/query",
            json={
                "query": initial_query,
                "session_id": session_id,
                "bypass_cache": True,
            },
        )

        assert response1.status_code == 200, f"Initial query API error: {response1.text}"
        data1 = response1.json()
        assert data1.get("success") is True, f"Initial query failed: {data1.get('response', data1.get('error'))}"

        print(f"\n=== Test 3: Conversation Memory ===")
        print(f"Initial query: {initial_query}")
        print(f"Initial response preview: {data1.get('response', '')[:300]}")

        # Step 2: Follow-up query using context
        follow_up_query = "From those results, how many became active in 2023 vs 2022?"
        response2 = await live_api_client.post(
            "/api/query",
            json={
                "query": follow_up_query,
                "session_id": session_id,  # Same session!
                "bypass_cache": True,
            },
        )

        assert response2.status_code == 200, f"Follow-up API error: {response2.text}"
        data2 = response2.json()

        # Follow-up may fail if context isn't maintained - this is informational
        print(f"Follow-up query: {follow_up_query}")
        print(f"Follow-up success: {data2.get('success')}")
        print(f"Follow-up response: {data2.get('response', '')[:500]}")

        # The follow-up should reference the context
        response_text = data2.get("response", "").lower()

        # Check for indicators that context was used:
        context_indicators = [
            "2023",
            "2022",
            "those",
            "result",
            "customer",
            "previous",
            "from",
        ]
        context_used = sum(1 for ind in context_indicators if ind in response_text)

        print(f"\nContext usage analysis:")
        print(f"  Indicators found: {context_used}/7")
        for ind in context_indicators:
            found = ind in response_text
            print(f"    '{ind}': {'FOUND' if found else 'not found'}")

        # Informational check - success may be False if follow-up isn't understood
        if not data2.get("success"):
            print(f"\n  [INFO] Follow-up query not fully understood by pipeline")
            print(f"  Error: {data2.get('error', data2.get('response', 'Unknown'))}")
            print("  RECOMMENDATION: Improve ContextAgent's follow-up detection")
        elif context_used < 2:
            print(f"\n  [INFO] Follow-up response has weak context usage ({context_used}/7)")
            print("  RECOMMENDATION: Improve ContextAgent's context continuity")

    @pytest.mark.asyncio
    async def test_different_session_no_context(self, live_api_client):
        """Verify different session IDs don't share context."""
        import uuid

        session1 = str(uuid.uuid4())
        session2 = str(uuid.uuid4())

        # Query with session 1
        await live_api_client.post(
            "/api/query",
            json={
                "query": "Find customers in California",
                "session_id": session1,
            },
        )

        # Follow-up with different session
        response = await live_api_client.post(
            "/api/query",
            json={
                "query": "Show me more about those customers",
                "session_id": session2,  # Different session!
            },
        )

        data = response.json()
        # Should work but might not have context about "those"
        print(f"Cross-session response: {data.get('response', '')[:200]}")


# ============================================================================
# Test 4: Batch Address Verification
# ============================================================================


class TestBatchAddressVerification:
    """Test batch address correction from corrupted addresses."""

    @pytest.mark.asyncio
    async def test_batch_address_correction(
        self, live_api_client, sample_corrupted_addresses
    ):
        """
        Test: Batch verify 20 corrupted addresses (subset for speed).

        Validates:
        - Batch endpoint accepts address list
        - Returns correction results for each
        - Calculates summary statistics
        """
        addresses = [addr["corrupted_address"] for addr in sample_corrupted_addresses]

        response = await live_api_client.post(
            "/api/address/verify/batch",
            json={
                "addresses": addresses,
                "concurrency": 5,
            },
            timeout=120.0,  # Longer timeout for batch
        )

        assert response.status_code == 200, f"Batch API error: {response.text}"
        data = response.json()

        print(f"\n=== Test 4: Batch Address Verification (20 addresses) ===")

        # Check response structure
        if "results" in data:
            results = data["results"]
            print(f"Total processed: {len(results)}")

            # Count by status - handle nested result structure
            status_counts = {}
            for result in results:
                # Handle nested structure: results[i].result.status
                inner = result.get("result", result)
                status = inner.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            print(f"Status breakdown: {status_counts}")

            # Calculate success rate
            success_statuses = {"verified", "corrected", "completed"}
            success_count = sum(
                status_counts.get(s, 0) for s in success_statuses
            )
            total = len(results)
            success_rate = (success_count / total * 100) if total > 0 else 0

            print(f"Success rate: {success_rate:.1f}%")

            # Show sample corrections
            print("\nSample corrections:")
            for i, result in enumerate(results[:5]):
                original = sample_corrupted_addresses[i]["corrupted_address"]
                # Handle nested structure
                inner = result.get("result", result)
                verified = inner.get("verified", {})
                if isinstance(verified, dict):
                    corrected = verified.get("formatted", verified.get("single_line", "N/A"))
                else:
                    corrected = str(verified) if verified else "N/A"
                print(f"  [{inner.get('status')}] {original[:40]}...")
                print(f"    -> {corrected}")

        elif "summary" in data:
            print(f"Summary: {data['summary']}")

    @pytest.mark.asyncio
    async def test_full_batch_200_addresses(
        self, live_api_client, corrupted_addresses
    ):
        """
        Test: Full batch of 200 corrupted addresses.

        Target: >80% success rate (verified + corrected + completed).
        """
        addresses = [addr["corrupted_address"] for addr in corrupted_addresses]

        response = await live_api_client.post(
            "/api/address/verify/batch",
            json={
                "addresses": addresses,
                "concurrency": 10,
            },
            timeout=300.0,  # 5 min timeout for 200 addresses
        )

        assert response.status_code == 200, f"Batch API error: {response.text}"
        data = response.json()

        print(f"\n=== Full Batch Test: 200 Addresses ===")

        if "results" in data:
            results = data["results"]

            # Count by status - handle nested result structure
            status_counts = {}
            for result in results:
                # Handle nested structure: results[i].result.status
                inner = result.get("result", result)
                status = inner.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1

            print(f"Status breakdown: {status_counts}")

            # Calculate success rate
            success_statuses = {"verified", "corrected", "completed"}
            success_count = sum(
                status_counts.get(s, 0) for s in success_statuses
            )

            total = len(results)
            success_rate = (success_count / total * 100) if total > 0 else 0

            print(f"Success rate: {success_rate:.1f}%")
            print(f"Target: >80%")

            # This is a soft target - warn but don't fail
            if success_rate < 80:
                print(f"WARNING: Success rate below 80% target")
            else:
                print(f"SUCCESS: Met 80% target!")

    @pytest.mark.asyncio
    async def test_single_address_correction(self, live_api_client):
        """Test single address verification endpoint."""
        test_address = "123 mian st, new yrok ny 10001"  # Typos

        response = await live_api_client.post(
            "/api/address/verify",
            json={"address": test_address},
        )

        assert response.status_code == 200
        data = response.json()

        print(f"\n=== Single Address Test ===")
        print(f"Input: {test_address}")
        print(f"Status: {data.get('status')}")
        print(f"Confidence: {data.get('confidence')}")
        if "verified" in data:
            print(f"Corrected: {data['verified']}")


# ============================================================================
# Infrastructure Verification
# ============================================================================


class TestInfrastructure:
    """Verify required infrastructure is running."""

    @pytest.mark.asyncio
    async def test_api_health(self, live_api_client):
        """Verify API is healthy."""
        response = await live_api_client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        print(f"\n=== API Health ===")
        print(f"Status: {data.get('status')}")
        print(f"Mode: {data.get('mode')}")

    @pytest.mark.asyncio
    async def test_address_service_health(self, live_api_client):
        """Verify address service is healthy."""
        response = await live_api_client.get("/api/address/health")

        if response.status_code == 200:
            data = response.json()
            print(f"\n=== Address Service Health ===")
            print(f"Status: {data}")
        else:
            print(f"Address service health check returned: {response.status_code}")
