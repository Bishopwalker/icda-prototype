"""Nova AI-powered address completion and correction.

This module uses AWS Bedrock Nova to intelligently complete partial
addresses, correct typos, and suggest the most likely full address
based on context clues like ZIP code, partial street names, etc.
"""

import json
import logging
import re
from typing import Any

import boto3
from botocore.exceptions import ClientError

from icda.address_models import (
    ParsedAddress,
    VerificationResult,
    VerificationStatus,
    AddressComponent,
)
from icda.address_index import AddressIndex, MatchResult
from icda.address_normalizer import AddressNormalizer


logger = logging.getLogger(__name__)


class NovaAddressCompleter:
    """Uses Nova AI to complete and correct partial addresses.

    This class handles the intelligent completion of addresses when
    exact matches aren't found, using context clues and fuzzy matching
    combined with Nova's reasoning capabilities.
    """

    _SYSTEM_PROMPT = """You are an address completion assistant. Your task is to analyze partial or incomplete US addresses and determine the most likely complete address.

Given:
1. A partial address input
2. A list of candidate addresses from the same ZIP code or area
3. Context clues (street number, partial street name, city, state, ZIP)

Your job:
- Identify which candidate address best matches the input
- Consider typos, abbreviations, and partial names
- Return the completed address in structured JSON format

Rules:
- Only suggest addresses from the provided candidates
- If no candidate is a good match, indicate low confidence
- Consider common typos (turkey -> Turkey Run, oak -> Oakland, etc.)
- Match street numbers exactly when provided
- ZIP code is a strong anchor - prioritize matches within the same ZIP"""

    _COMPLETION_PROMPT = """Analyze this partial address and find the best match:

INPUT ADDRESS:
{input_address}

PARSED COMPONENTS:
- Street Number: {street_number}
- Partial Street: {street_name}
- City: {city}
- State: {state}
- ZIP: {zip_code}

CANDIDATE ADDRESSES IN THIS AREA:
{candidates}

Based on the input and candidates, determine the most likely complete address.

Respond with JSON only:
{{
    "matched": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation",
    "completed_address": {{
        "street_number": "...",
        "street_name": "...",
        "street_type": "...",
        "city": "...",
        "state": "...",
        "zip_code": "..."
    }},
    "alternatives": [
        {{"address": "full address string", "confidence": 0.0-1.0}}
    ]
}}"""

    def __init__(
        self,
        region: str,
        model_id: str,
        address_index: AddressIndex,
    ):
        """Initialize Nova address completer.

        Args:
            region: AWS region for Bedrock.
            model_id: Nova model ID to use.
            address_index: Index of known addresses.
        """
        self.region = region
        self.model_id = model_id
        self.index = address_index
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self.available = True

        logger.info(f"NovaAddressCompleter initialized with model {model_id}")

    async def complete_address(
        self,
        parsed: ParsedAddress,
        fuzzy_matches: list[MatchResult],
    ) -> VerificationResult:
        """Use Nova to complete a partial address.

        Args:
            parsed: Partially parsed address.
            fuzzy_matches: Candidate matches from fuzzy search.

        Returns:
            VerificationResult with completed address.
        """
        if not self.available:
            return self._fallback_completion(parsed, fuzzy_matches)

        # Build candidate list for Nova
        candidates = self._format_candidates(fuzzy_matches)

        # If we have a ZIP but limited candidates, get more from ZIP
        if parsed.zip_code and len(fuzzy_matches) < 5:
            zip_addresses = self.index.lookup_by_zip(parsed.zip_code)
            additional = [
                f"- {addr.parsed.single_line}"
                for addr in zip_addresses[:10]
                if addr not in [m.address for m in fuzzy_matches]
            ]
            if additional:
                candidates += "\n" + "\n".join(additional)

        # Build the prompt
        prompt = self._COMPLETION_PROMPT.format(
            input_address=parsed.raw,
            street_number=parsed.street_number or "unknown",
            street_name=parsed.street_name or "unknown",
            city=parsed.city or "unknown",
            state=parsed.state or "unknown",
            zip_code=parsed.zip_code or "unknown",
            candidates=candidates or "No candidates available",
        )

        try:
            response = self._call_nova(prompt)
            return self._parse_completion_response(response, parsed, fuzzy_matches)
        except ClientError as e:
            logger.error(f"Nova API error: {e}")
            self.available = False
            return self._fallback_completion(parsed, fuzzy_matches)
        except Exception as e:
            logger.error(f"Address completion error: {e}")
            return self._fallback_completion(parsed, fuzzy_matches)

    async def suggest_street_completion(
        self,
        partial_street: str,
        zip_code: str,
        street_number: str | None = None,
    ) -> list[dict[str, Any]]:
        """Suggest complete street names for a partial input.

        This is the key method for completing "turkey" -> "Turkey Run"
        within a specific ZIP code.

        Args:
            partial_street: Partial street name (e.g., "turkey").
            zip_code: ZIP code for context.
            street_number: Optional street number.

        Returns:
            List of suggestions with confidence scores.
        """
        # First, try index-based suggestions
        suggestions = self.index.get_street_suggestions(partial_street, zip_code, 10)

        if suggestions:
            # Found matches in index - return them with confidence
            return [
                {
                    "street_name": s,
                    "confidence": 0.9 if s.lower().startswith(partial_street.lower()) else 0.7,
                    "source": "index",
                }
                for s in suggestions
            ]

        # No index matches - try Nova for creative completion
        if self.available:
            try:
                return await self._nova_street_suggestion(
                    partial_street,
                    zip_code,
                    street_number,
                )
            except Exception as e:
                logger.warning(f"Nova street suggestion failed: {e}")

        return []

    async def _nova_street_suggestion(
        self,
        partial: str,
        zip_code: str,
        street_number: str | None,
    ) -> list[dict[str, Any]]:
        """Use Nova to suggest street completions."""
        # Get all streets in this ZIP for context
        zip_addresses = self.index.lookup_by_zip(zip_code)
        streets = set()
        for addr in zip_addresses:
            if addr.parsed.street_name:
                full = addr.parsed.street_name
                if addr.parsed.street_type:
                    full += f" {addr.parsed.street_type}"
                streets.add(full)

        prompt = f"""Given the partial street name "{partial}" in ZIP code {zip_code}, suggest the most likely complete street name.

Known streets in this ZIP:
{chr(10).join(f'- {s}' for s in sorted(streets)[:20])}

Consider:
- Common typos and abbreviations
- Phonetic similarities
- Prefix/suffix matches

Respond with JSON:
{{
    "suggestions": [
        {{"street_name": "...", "confidence": 0.0-1.0, "reason": "..."}}
    ]
}}"""

        try:
            response = self._call_nova(prompt)
            data = self._extract_json(response)
            if data and "suggestions" in data:
                return [
                    {
                        "street_name": s["street_name"],
                        "confidence": s.get("confidence", 0.5),
                        "source": "nova",
                    }
                    for s in data["suggestions"]
                ]
        except Exception as e:
            logger.warning(f"Nova suggestion parsing failed: {e}")

        return []

    def _call_nova(self, prompt: str) -> str:
        """Make a call to Nova API."""
        response = self._client.converse(
            modelId=self.model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            system=[{"text": self._SYSTEM_PROMPT}],
            inferenceConfig={"maxTokens": 1024, "temperature": 0.1},
        )

        content = response["output"]["message"]["content"]
        for block in content:
            if "text" in block:
                return block["text"]
        return ""

    def _format_candidates(self, matches: list[MatchResult]) -> str:
        """Format candidate matches for the prompt."""
        if not matches:
            return "No candidates available"

        lines = []
        for m in matches[:10]:  # Limit to top 10
            addr = m.address.parsed
            lines.append(f"- {addr.single_line} (score: {m.score:.2f})")
        return "\n".join(lines)

    def _parse_completion_response(
        self,
        response: str,
        original: ParsedAddress,
        fuzzy_matches: list[MatchResult],
    ) -> VerificationResult:
        """Parse Nova's completion response."""
        data = self._extract_json(response)

        if not data or not data.get("matched"):
            # Nova couldn't find a good match
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                original=original,
                confidence=data.get("confidence", 0.0) if data else 0.0,
                metadata={
                    "reason": data.get("reasoning", "No match found") if data else "Parse error",
                    "model": self.model_id,
                },
            )

        # Extract completed address
        completed_data = data.get("completed_address", {})
        completed = ParsedAddress(
            raw=original.raw,
            street_number=completed_data.get("street_number"),
            street_name=completed_data.get("street_name"),
            street_type=completed_data.get("street_type"),
            city=completed_data.get("city"),
            state=completed_data.get("state"),
            zip_code=completed_data.get("zip_code"),
        )

        # Determine status based on what was completed
        confidence = data.get("confidence", 0.5)
        if confidence >= 0.9:
            status = VerificationStatus.COMPLETED
        elif confidence >= 0.7:
            status = VerificationStatus.CORRECTED
        else:
            status = VerificationStatus.SUGGESTED

        # Extract alternatives
        alternatives = []
        for alt in data.get("alternatives", []):
            if isinstance(alt, dict) and "address" in alt:
                alt_parsed = AddressNormalizer.normalize(alt["address"])
                alternatives.append(alt_parsed)

        return VerificationResult(
            status=status,
            original=original,
            verified=completed,
            confidence=confidence,
            match_type="nova_completion",
            alternatives=alternatives[:3],
            metadata={
                "reasoning": data.get("reasoning", ""),
                "model": self.model_id,
            },
        )

    def _fallback_completion(
        self,
        parsed: ParsedAddress,
        fuzzy_matches: list[MatchResult],
    ) -> VerificationResult:
        """Fallback completion when Nova is unavailable."""
        if not fuzzy_matches:
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                original=parsed,
                confidence=0.0,
                metadata={"reason": "No candidates available"},
            )

        # Use best fuzzy match
        best = fuzzy_matches[0]

        # Determine status based on score
        if best.score >= 0.95:
            status = VerificationStatus.VERIFIED
        elif best.score >= 0.8:
            status = VerificationStatus.CORRECTED
        elif best.score >= 0.6:
            status = VerificationStatus.SUGGESTED
        else:
            status = VerificationStatus.UNVERIFIED

        alternatives = [m.address.parsed for m in fuzzy_matches[1:4]]

        return VerificationResult(
            status=status,
            original=parsed,
            verified=best.address.parsed,
            confidence=best.score,
            match_type=best.match_type,
            alternatives=alternatives,
            metadata={
                "customer_id": best.customer_id,
                "fallback": True,
            },
        )

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON from Nova response text."""
        # Try to find JSON block
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try parsing entire response
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
