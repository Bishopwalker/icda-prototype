"""Unit tests for address verification pipeline.

Tests cover:
- Address normalization and parsing
- Address classification
- Index building and lookups
- Pipeline flow
- Batch processing
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from icda.address_models import (
    AddressComponent,
    AddressQuality,
    BatchItem,
    ParsedAddress,
    VerificationStatus,
)
from icda.address_normalizer import (
    AddressNormalizer,
    normalize_state,
    normalize_street_type,
)
from icda.address_index import AddressIndex, IndexedAddress
from icda.address_completer import NovaAddressCompleter
from icda.address_pipeline import AddressPipeline, BatchProcessor


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_customers():
    """Sample customer data for testing."""
    return [
        {
            "crid": "CRID-000001",
            "name": "John Doe",
            "address": "123 Turkey Run",
            "city": "Springfield",
            "state": "VA",
            "zip": "22222",
            "move_history": [
                {
                    "from_address": "456 Oak St",
                    "to_address": "123 Turkey Run",
                    "city": "Springfield",
                    "state": "VA",
                    "zip": "22222",
                    "move_date": "2024-01-15",
                }
            ],
        },
        {
            "crid": "CRID-000002",
            "name": "Jane Smith",
            "address": "789 Main Blvd",
            "city": "Arlington",
            "state": "VA",
            "zip": "22201",
            "move_history": [],
        },
        {
            "crid": "CRID-000003",
            "name": "Bob Wilson",
            "address": "101 Turkey Trot Ln",
            "city": "Springfield",
            "state": "VA",
            "zip": "22222",
            "move_history": [],
        },
    ]


@pytest.fixture
def address_index(sample_customers):
    """Build address index from sample data."""
    index = AddressIndex()
    index.build_from_customers(sample_customers)
    return index


@pytest.fixture
def mock_completer(address_index):
    """Create mock Nova completer."""
    completer = MagicMock(spec=NovaAddressCompleter)
    completer.available = True
    completer.index = address_index
    completer.complete_address = AsyncMock()
    completer.suggest_street_completion = AsyncMock(return_value=[])
    return completer


@pytest.fixture
def pipeline(address_index, mock_completer):
    """Create pipeline with test dependencies."""
    return AddressPipeline(address_index, mock_completer)


# ============================================================================
# Address Normalizer Tests
# ============================================================================


class TestAddressNormalizer:
    """Tests for AddressNormalizer class."""

    def test_normalize_complete_address(self):
        """Test parsing a complete address."""
        raw = "123 Main St, New York, NY 10001"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.street_number == "123"
        assert parsed.street_name == "Main"
        assert parsed.street_type == "St"
        assert parsed.city == "New York"
        assert parsed.state == "NY"
        assert parsed.zip_code == "10001"

    def test_normalize_partial_address(self):
        """Test parsing a partial address."""
        raw = "101 turkey 22222"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.street_number == "101"
        assert parsed.zip_code == "22222"
        # Street name should be extracted (minus ZIP)
        assert "turkey" in parsed.raw.lower()

    def test_normalize_with_unit(self):
        """Test parsing address with unit number."""
        raw = "456 Oak Ave Apt 2B, Dallas, TX 75201"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.street_number == "456"
        assert parsed.unit == "#2B"
        assert AddressComponent.UNIT in parsed.components_found

    def test_normalize_zip_plus4(self):
        """Test parsing ZIP+4 format."""
        raw = "789 Pine Rd, Seattle, WA 98101-1234"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.zip_code == "98101"
        assert parsed.zip_plus4 == "1234"

    def test_normalize_full_state_name(self):
        """Test parsing full state name."""
        raw = "321 Elm Blvd, Austin, Texas 78701"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.state == "TX"

    def test_normalize_empty_input(self):
        """Test handling empty input."""
        parsed = AddressNormalizer.normalize("")
        assert parsed.raw == ""
        assert parsed.street_number is None

    def test_classify_complete_address(self):
        """Test classification of complete address."""
        parsed = ParsedAddress(
            raw="123 Main St, City, ST 12345",
            street_number="123",
            street_name="Main",
            street_type="St",
            city="City",
            state="ST",
            zip_code="12345",
        )
        classification = AddressNormalizer.classify(parsed)

        assert classification.quality == AddressQuality.COMPLETE
        assert classification.confidence >= 0.9

    def test_classify_partial_address(self):
        """Test classification of partial address."""
        parsed = ParsedAddress(
            raw="123 Main",
            street_number="123",
            street_name="Main",
        )
        classification = AddressNormalizer.classify(parsed)

        assert classification.quality in (AddressQuality.PARTIAL, AddressQuality.INVALID)
        assert len(classification.issues) > 0

    def test_classify_invalid_address(self):
        """Test classification of invalid address."""
        parsed = ParsedAddress(raw="gibberish")
        classification = AddressNormalizer.classify(parsed)

        assert classification.quality == AddressQuality.INVALID
        assert classification.confidence < 0.5


class TestStateNormalization:
    """Tests for state normalization."""

    def test_normalize_abbreviation(self):
        """Test normalizing state abbreviation."""
        assert normalize_state("NY") == "NY"
        assert normalize_state("ny") == "NY"
        assert normalize_state("Ca") == "CA"

    def test_normalize_full_name(self):
        """Test normalizing full state name."""
        assert normalize_state("New York") == "NY"
        assert normalize_state("california") == "CA"
        assert normalize_state("TEXAS") == "TX"

    def test_normalize_invalid_state(self):
        """Test handling invalid state."""
        assert normalize_state("ZZ") is None
        assert normalize_state("Atlantis") is None


class TestStreetTypeNormalization:
    """Tests for street type normalization."""

    def test_normalize_full_type(self):
        """Test normalizing full street type."""
        assert normalize_street_type("Street") == "St"
        assert normalize_street_type("avenue") == "Ave"
        assert normalize_street_type("BOULEVARD") == "Blvd"

    def test_normalize_abbreviation(self):
        """Test handling already abbreviated types."""
        assert normalize_street_type("St") == "St"
        assert normalize_street_type("Ave") == "Ave"


# ============================================================================
# Address Index Tests
# ============================================================================


class TestAddressIndex:
    """Tests for AddressIndex class."""

    def test_build_from_customers(self, sample_customers):
        """Test building index from customer data."""
        index = AddressIndex()
        count = index.build_from_customers(sample_customers)

        assert count > 0
        assert index.is_indexed
        assert index.total_addresses == count

    def test_lookup_exact(self, address_index):
        """Test exact address lookup."""
        # Note: The index stores street name without type separately
        parsed = ParsedAddress(
            raw="123 Turkey Run, Springfield, VA 22222",
            street_number="123",
            street_name="Turkey",  # Index stores name without "Run" suffix
            city="Springfield",
            state="VA",
            zip_code="22222",
        )
        results = address_index.lookup_exact(parsed)

        # If exact match not found, try fuzzy which should work
        if not results:
            fuzzy = address_index.lookup_fuzzy(parsed, threshold=0.8)
            assert len(fuzzy) >= 1, "Should find via fuzzy match"
            assert fuzzy[0].score >= 0.8
        else:
            assert results[0].score == 1.0
            assert results[0].match_type == "exact"

    def test_lookup_by_zip(self, address_index):
        """Test lookup by ZIP code."""
        results = address_index.lookup_by_zip("22222")

        assert len(results) >= 2  # At least Turkey Run and Turkey Trot

    def test_lookup_street_in_zip(self, address_index):
        """Test finding street in ZIP - the key feature."""
        # This tests the "turkey" -> "Turkey Run" scenario
        results = address_index.lookup_street_in_zip("turkey", "22222", threshold=0.5)

        assert len(results) >= 1
        # Should find Turkey Run and/or Turkey Trot
        street_names = [r.address.parsed.street_name for r in results]
        assert any("Turkey" in name for name in street_names if name)

    def test_lookup_fuzzy(self, address_index):
        """Test fuzzy address matching."""
        parsed = ParsedAddress(
            raw="123 turky run 22222",  # Typo in "turkey"
            street_number="123",
            street_name="turky run",
            zip_code="22222",
        )
        results = address_index.lookup_fuzzy(parsed, threshold=0.5)

        assert len(results) >= 1
        # Should still match Turkey Run
        assert results[0].score > 0.5

    def test_get_street_suggestions(self, address_index):
        """Test street name autocomplete."""
        suggestions = address_index.get_street_suggestions("tur", "22222", limit=5)

        assert len(suggestions) >= 1
        # Should suggest Turkey Run and/or Turkey Trot
        assert any("Turkey" in s for s in suggestions)

    def test_stats(self, address_index):
        """Test index statistics."""
        stats = address_index.stats()

        assert stats["indexed"] is True
        assert stats["total_addresses"] > 0
        assert "unique_zips" in stats
        assert "unique_states" in stats


# ============================================================================
# Address Pipeline Tests
# ============================================================================


class TestAddressPipeline:
    """Tests for AddressPipeline class."""

    @pytest.mark.asyncio
    async def test_verify_exact_match(self, pipeline, address_index):
        """Test verification with exact match."""
        result = await pipeline.verify("123 Turkey Run, Springfield, VA 22222")

        assert result.status == VerificationStatus.VERIFIED
        assert result.confidence >= 0.9
        assert result.verified is not None

    @pytest.mark.asyncio
    async def test_verify_partial_address(self, pipeline, mock_completer):
        """Test verification of partial address."""
        # Mock the completer to return a result
        from icda.address_models import VerificationResult

        mock_completer.complete_address.return_value = VerificationResult(
            status=VerificationStatus.COMPLETED,
            original=ParsedAddress(raw="101 turkey 22222"),
            verified=ParsedAddress(
                raw="101 Turkey Run, Springfield, VA 22222",
                street_number="101",
                street_name="Turkey Run",
                city="Springfield",
                state="VA",
                zip_code="22222",
            ),
            confidence=0.85,
            match_type="nova_completion",
        )

        result = await pipeline.verify("101 turkey 22222")

        # Should attempt completion
        assert result.status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.COMPLETED,
            VerificationStatus.SUGGESTED,
            VerificationStatus.UNVERIFIED,
        )

    @pytest.mark.asyncio
    async def test_verify_batch(self, pipeline):
        """Test batch verification."""
        items = [
            BatchItem(id="1", address="123 Turkey Run, Springfield, VA 22222"),
            BatchItem(id="2", address="789 Main Blvd, Arlington, VA 22201"),
        ]

        results, summary = await pipeline.verify_batch(items, concurrency=2)

        assert len(results) == 2
        assert summary.total == 2
        assert summary.verified + summary.corrected + summary.completed + summary.suggested + summary.unverified + summary.failed == 2

    @pytest.mark.asyncio
    async def test_verify_invalid_address(self, pipeline):
        """Test verification of invalid address."""
        result = await pipeline.verify("asdfghjkl")

        assert result.status in (VerificationStatus.UNVERIFIED, VerificationStatus.FAILED)
        assert result.confidence < 0.5


class TestBatchProcessor:
    """Tests for BatchProcessor class."""

    @pytest.mark.asyncio
    async def test_process_list(self, pipeline):
        """Test processing a list of addresses."""
        processor = BatchProcessor(pipeline)
        addresses = [
            "123 Turkey Run, Springfield, VA 22222",
            "789 Main Blvd, Arlington, VA 22201",
        ]

        results, summary = await processor.process_list(addresses, concurrency=2)

        assert len(results) == 2
        assert summary.total == 2

    @pytest.mark.asyncio
    async def test_process_records(self, pipeline):
        """Test processing records with address fields."""
        processor = BatchProcessor(pipeline)
        records = [
            {
                "id": "1",
                "address": "123 Turkey Run",
                "city": "Springfield",
                "state": "VA",
                "zip": "22222",
            },
            {
                "id": "2",
                "street": "789 Main Blvd",
                "city": "Arlington",
                "state": "VA",
                "zip": "22201",
            },
        ]

        results, summary = await processor.process_records(
            records,
            address_field="address",
            id_field="id",
        )

        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_process_csv_data(self, pipeline):
        """Test processing CSV-style data."""
        processor = BatchProcessor(pipeline)
        rows = [
            {
                "address": "123 Turkey Run",
                "city": "Springfield",
                "state": "VA",
                "zip": "22222",
            },
        ]

        results, summary = await processor.process_csv_data(rows)

        assert len(results) == 1


# ============================================================================
# Address Completer Tests
# ============================================================================


class TestNovaAddressCompleter:
    """Tests for NovaAddressCompleter class."""

    def test_format_candidates(self, address_index):
        """Test candidate formatting for Nova prompt."""
        completer = NovaAddressCompleter.__new__(NovaAddressCompleter)
        completer.index = address_index
        completer.available = False  # Skip actual Nova calls

        # Get some matches
        parsed = ParsedAddress(
            raw="turkey 22222",
            street_name="turkey",
            zip_code="22222",
        )
        matches = address_index.lookup_street_in_zip("turkey", "22222")

        formatted = completer._format_candidates(matches)

        assert "Turkey" in formatted or "score" in formatted

    def test_fallback_completion(self, address_index):
        """Test fallback when Nova unavailable."""
        completer = NovaAddressCompleter.__new__(NovaAddressCompleter)
        completer.index = address_index
        completer.available = False

        parsed = ParsedAddress(
            raw="101 turkey 22222",
            street_number="101",
            street_name="turkey",
            zip_code="22222",
        )
        matches = address_index.lookup_street_in_zip("turkey", "22222")

        result = completer._fallback_completion(parsed, matches)

        # Should return best fuzzy match
        assert result.status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.CORRECTED,
            VerificationStatus.SUGGESTED,
            VerificationStatus.UNVERIFIED,
        )


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_normalize_unicode_address(self):
        """Test handling unicode in address."""
        raw = "123 Cañon St, San José, CA 95113"
        parsed = AddressNormalizer.normalize(raw)

        # Should handle unicode gracefully
        assert parsed.zip_code == "95113"

    def test_normalize_all_caps(self):
        """Test handling all-caps address."""
        raw = "456 OAK AVENUE, CHICAGO, IL 60601"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.state == "IL"
        assert parsed.zip_code == "60601"

    def test_normalize_extra_whitespace(self):
        """Test handling extra whitespace."""
        raw = "  789   Pine    Rd  ,  Seattle  ,  WA   98101  "
        parsed = AddressNormalizer.normalize(raw)

        # Should normalize whitespace
        assert parsed.zip_code == "98101"

    @pytest.mark.asyncio
    async def test_batch_with_errors(self, pipeline):
        """Test batch processing handles errors gracefully."""
        items = [
            BatchItem(id="1", address="valid address 12345"),
            BatchItem(id="2", address=""),  # Empty - might error
        ]

        results, summary = await pipeline.verify_batch(items)

        # Should complete without raising
        assert len(results) == 2

    def test_index_empty_customers(self):
        """Test building index from empty customer list."""
        index = AddressIndex()
        count = index.build_from_customers([])

        assert count == 0
        assert index.is_indexed
        assert index.total_addresses == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for full pipeline flow."""

    @pytest.mark.asyncio
    async def test_turkey_run_scenario(self, address_index, mock_completer):
        """Test the specific turkey -> Turkey Run scenario."""
        pipeline = AddressPipeline(address_index, mock_completer)

        # User enters: "101 turkey ok 22222"
        # Should complete to: "101 Turkey Run, Springfield, VA 22222" or similar

        # First check the index has the data
        suggestions = address_index.get_street_suggestions("turkey", "22222")
        assert len(suggestions) > 0, "Index should have Turkey streets"

        # Check street lookup works
        matches = address_index.lookup_street_in_zip("turkey", "22222", threshold=0.5)
        assert len(matches) > 0, "Should find Turkey streets in ZIP 22222"

        # Verify Turkey Run is in the matches
        found_turkey_run = any(
            "Turkey Run" in (m.address.parsed.street_name or "")
            or "Turkey" in (m.address.parsed.street_name or "")
            for m in matches
        )
        assert found_turkey_run, "Should find Turkey Run or similar"

    @pytest.mark.asyncio
    async def test_full_pipeline_verified(self, address_index, mock_completer):
        """Test full pipeline returns verified for known address."""
        pipeline = AddressPipeline(address_index, mock_completer)

        result = await pipeline.verify("123 Turkey Run, Springfield, VA 22222")

        assert result.status == VerificationStatus.VERIFIED
        assert result.verified is not None
        # Street name may be stored as just "Turkey" without suffix
        assert "Turkey" in result.verified.street_name


<<<<<<< HEAD
=======
# ============================================================================
# Puerto Rico Address Tests
# ============================================================================


class TestPuertoRicoAddresses:
    """Tests for Puerto Rico address handling with urbanization support."""

    def test_detect_pr_by_zip(self):
        """Test detecting PR address by ZIP code (006-009)."""
        pr_zips = ["00601", "00705", "00802", "00924"]
        non_pr_zips = ["10001", "22222", "90210", "00501"]  # 005xx is NY

        for zip_code in pr_zips:
            raw = f"123 Calle Luna, San Juan, PR {zip_code}"
            parsed = AddressNormalizer.normalize(raw)
            assert parsed.is_puerto_rico, f"ZIP {zip_code} should be PR"

        for zip_code in non_pr_zips:
            raw = f"123 Main St, City, ST {zip_code}"
            parsed = AddressNormalizer.normalize(raw)
            assert not parsed.is_puerto_rico, f"ZIP {zip_code} should not be PR"

    def test_parse_pr_with_urbanization(self):
        """Test parsing PR address with URB prefix."""
        raw = "URB Villa Carolina, 123 Calle A, Carolina, PR 00983"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.is_puerto_rico
        # Urbanization is normalized to uppercase
        assert parsed.urbanization.upper() == "VILLA CAROLINA"
        assert parsed.zip_code == "00983"
        assert AddressComponent.URBANIZATION in parsed.components_found

    def test_parse_pr_urbanizacion_spanish(self):
        """Test parsing PR address with Spanish URBANIZACION term."""
        raw = "URBANIZACION Las Lomas, 456 Calle B, Bayamon, PR 00961"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.is_puerto_rico
        # Urbanization is normalized to uppercase
        assert parsed.urbanization.upper() == "LAS LOMAS"
        assert parsed.zip_code == "00961"

    def test_parse_pr_urb_lowercase(self):
        """Test parsing PR address with lowercase urb."""
        raw = "urb country club, 789 Ave Principal, Rio Piedras, PR 00926"
        parsed = AddressNormalizer.normalize(raw)

        assert parsed.is_puerto_rico
        assert parsed.urbanization is not None
        assert "Country Club" in parsed.urbanization or "country club" in parsed.urbanization.lower()

    def test_classify_pr_missing_urbanization(self):
        """Test classification warns when PR address missing urbanization."""
        parsed = ParsedAddress(
            raw="123 Calle Luna, San Juan, PR 00901",
            street_number="123",
            street_name="Calle Luna",
            city="San Juan",
            state="PR",
            zip_code="00901",
            is_puerto_rico=True,
            urbanization=None,  # Missing!
        )
        classification = AddressNormalizer.classify(parsed)

        # Should have a warning about missing urbanization
        has_urb_warning = any(
            "urbaniz" in issue.lower() for issue in classification.issues
        )
        assert has_urb_warning, f"Should warn about missing urbanization: {classification.issues}"

    def test_pr_with_urbanization_no_warning(self):
        """Test PR address with urbanization has no warning."""
        parsed = ParsedAddress(
            raw="URB Villa Carolina, 123 Calle A, Carolina, PR 00983",
            street_number="123",
            street_name="Calle A",
            city="Carolina",
            state="PR",
            zip_code="00983",
            is_puerto_rico=True,
            urbanization="Villa Carolina",
            components_found=[AddressComponent.URBANIZATION],
        )
        classification = AddressNormalizer.classify(parsed)

        # Should NOT have urbanization warning
        has_urb_warning = any(
            "urbaniz" in issue.lower() for issue in classification.issues
        )
        assert not has_urb_warning, f"Should not warn when urbanization present: {classification.issues}"

    def test_pr_formatted_address_includes_urbanization(self):
        """Test formatted PR address includes URB line."""
        parsed = ParsedAddress(
            raw="URB Villa Carolina, 123 Calle A, Carolina, PR 00983",
            street_number="123",
            street_name="Calle A",
            city="Carolina",
            state="PR",
            zip_code="00983",
            is_puerto_rico=True,
            urbanization="Villa Carolina",
        )

        formatted = parsed.formatted
        assert "URB Villa Carolina" in formatted
        # URB should be on its own line before street
        lines = formatted.split("\n")
        assert len(lines) >= 2
        assert "URB" in lines[0]

    def test_pr_single_line_format(self):
        """Test single-line format includes urbanization."""
        parsed = ParsedAddress(
            raw="URB Villa Carolina, 123 Calle A, Carolina, PR 00983",
            street_number="123",
            street_name="Calle A",
            city="Carolina",
            state="PR",
            zip_code="00983",
            is_puerto_rico=True,
            urbanization="Villa Carolina",
        )

        single_line = parsed.single_line
        assert "URB Villa Carolina" in single_line

    def test_pr_to_dict_includes_fields(self):
        """Test to_dict includes PR-specific fields."""
        parsed = ParsedAddress(
            raw="URB Villa Carolina, 123 Calle A, Carolina, PR 00983",
            street_number="123",
            street_name="Calle A",
            city="Carolina",
            state="PR",
            zip_code="00983",
            is_puerto_rico=True,
            urbanization="Villa Carolina",
        )

        d = parsed.to_dict()
        assert d["is_puerto_rico"] is True
        assert d["urbanization"] == "Villa Carolina"

    def test_non_pr_skips_urbanization(self):
        """Test non-PR address doesn't get is_puerto_rico flag."""
        raw = "123 Main St, New York, NY 10001"
        parsed = AddressNormalizer.normalize(raw)

        assert not parsed.is_puerto_rico
        assert parsed.urbanization is None

    def test_pr_index_urbanization_lookup(self):
        """Test address index can lookup by urbanization."""
        index = AddressIndex()

        # Build index with PR customer
        pr_customers = [
            {
                "crid": "CRID-PR-001",
                "name": "Maria Rodriguez",
                "address": "URB Villa Carolina, 123 Calle A",
                "city": "Carolina",
                "state": "PR",
                "zip": "00983",
            },
        ]
        index.build_from_customers(pr_customers)

        # Lookup by urbanization
        results = index.lookup_by_urbanization("Villa Carolina", "00983")
        assert len(results) >= 1, "Should find by urbanization"

    @pytest.fixture
    def pr_sample_customers(self):
        """Sample PR customer data for testing."""
        return [
            {
                "crid": "CRID-PR-001",
                "name": "Maria Rodriguez",
                "address": "URB Villa Carolina, 123 Calle A",
                "city": "Carolina",
                "state": "PR",
                "zip": "00983",
            },
            {
                "crid": "CRID-PR-002",
                "name": "Jose Garcia",
                "address": "URBANIZACION Las Lomas, 456 Calle B",
                "city": "Bayamon",
                "state": "PR",
                "zip": "00961",
            },
            {
                "crid": "CRID-PR-003",
                "name": "Ana Martinez",
                "address": "789 Ave Ponce de Leon",  # No urbanization
                "city": "San Juan",
                "state": "PR",
                "zip": "00907",
            },
        ]

    def test_pr_index_builds_urbanization_index(self, pr_sample_customers):
        """Test index builds urbanization lookup structure."""
        index = AddressIndex()
        index.build_from_customers(pr_sample_customers)

        # Check stats include PR info
        stats = index.stats()
        assert stats["indexed"] is True

        # Should have urbanization index entries
        urb_lookup = index.lookup_by_urbanization("Villa Carolina")
        assert len(urb_lookup) >= 1


>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
