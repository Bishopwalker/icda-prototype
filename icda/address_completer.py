"""Nova AI-powered address completion and correction.

Supports LITE MODE (no AWS) with fallback to fuzzy matching only.
"""

import json
import logging
import os
import re
from typing import Any

from icda.address_models import (
    ParsedAddress,
    VerificationResult,
    VerificationStatus,
)
from icda.address_index import AddressIndex, MatchResult
from icda.address_normalizer import AddressNormalizer


logger = logging.getLogger(__name__)


class NovaAddressCompleter:
    """Uses Nova AI to complete and correct partial addresses.
    
    Falls back to fuzzy matching if AWS credentials are not available.
    """

    _SYSTEM_PROMPT = """You are an address verification assistant. Your task is to determine if a partial address matches any REAL address from the provided candidates.

Given:
1. A partial address input
2. A list of REAL candidate addresses from our database
3. Context clues (street number, partial street name, city, state, ZIP)

Your job:
- ONLY match against the provided candidate addresses - do NOT invent addresses
- If the input matches a candidate (considering typos, abbreviations), return that exact candidate
- If NO candidate is a good match, set matched=false and confidence=0

CRITICAL RULES:
- NEVER invent or fabricate an address that isn't in the candidates list
- If matched=true, the completed_address MUST be copied exactly from a candidate
- Street numbers must match exactly (101 cannot match 102)
- If uncertain, set matched=false - it's better to reject than accept a bad match
- Confidence should be 0.9+ only for very clear matches"""

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
        self._client = None
        self.available = False

        # Check if AWS credentials are available (supports default credential chain)
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError
            session = boto3.Session()
            if session.get_credentials() is None:
                logger.info("NovaAddressCompleter: No AWS credentials - using fallback mode")
                return
            self._client = boto3.client("bedrock-runtime", region_name=region)
            self.available = True
            logger.info(f"NovaAddressCompleter initialized with model {model_id}")
        except NoCredentialsError:
            logger.info("NovaAddressCompleter: AWS credentials not found - using fallback mode")
        except Exception as e:
            logger.warning(f"NovaAddressCompleter init failed: {e} - using fallback mode")

    async def complete_address(
        self,
        parsed: ParsedAddress,
        fuzzy_matches: list[MatchResult],
    ) -> VerificationResult:
        """Use Nova to complete a partial address (or fallback to fuzzy)."""
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
            from botocore.exceptions import ClientError
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
        """Suggest complete street names for a partial input."""
        # First, try index-based suggestions
        suggestions = self.index.get_street_suggestions(partial_street, zip_code, 10)

        if suggestions:
            return [
                {
                    "street_name": s,
                    "confidence": 0.9 if s.lower().startswith(partial_street.lower()) else 0.7,
                    "source": "index",
                }
                for s in suggestions
            ]

        # No index matches - try Nova for creative completion (if available)
        if self.available:
            try:
                return await self._nova_street_suggestion(partial_street, zip_code, street_number)
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
        if not self._client:
            return ""
            
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
        for m in matches[:10]:
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
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                original=original,
                confidence=data.get("confidence", 0.0) if data else 0.0,
                metadata={
                    "reason": data.get("reasoning", "No match found") if data else "Parse error",
                    "model": self.model_id,
                },
            )

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

        confidence = data.get("confidence", 0.5)
        if confidence >= 0.9:
            status = VerificationStatus.COMPLETED
        elif confidence >= 0.7:
            status = VerificationStatus.CORRECTED
        else:
            status = VerificationStatus.SUGGESTED

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
        """Fallback completion when Nova is unavailable.

        Uses STRICT thresholds - we only mark as verified/corrected
        if we have high confidence the address is real.
        """
        if not fuzzy_matches:
            return VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                original=parsed,
                confidence=0.0,
                metadata={
                    "reason": "No matching addresses found in database",
                    "fallback": True,
                    "suggestion": "Try providing more details (street number, ZIP code)",
                },
            )

        best = fuzzy_matches[0]

        # STRICT thresholds - only accept very high confidence matches
        if best.score >= 0.95:
            # Near-perfect match - this is a real address
            status = VerificationStatus.VERIFIED
        elif best.score >= 0.85:
            # High confidence - likely a real address with minor typos
            status = VerificationStatus.CORRECTED
        elif best.score >= 0.75:
            # Moderate confidence - suggest but mark as unconfirmed
            status = VerificationStatus.SUGGESTED
        else:
            # Below threshold - mark as unverified
            # Still show alternatives so user can pick
            status = VerificationStatus.UNVERIFIED

        alternatives = [m.address.parsed for m in fuzzy_matches[1:4]]

        # For unverified, don't claim we "verified" anything
        verified_addr = best.address.parsed if status != VerificationStatus.UNVERIFIED else None

        return VerificationResult(
            status=status,
            original=parsed,
            verified=verified_addr,
            confidence=best.score,
            match_type=best.match_type,
            alternatives=alternatives,
            metadata={
                "customer_id": best.customer_id,
                "fallback": True,
                "best_match": best.address.parsed.single_line if best.score >= 0.5 else None,
                "reason": self._get_match_reason(best.score),
            },
        )

    def _get_match_reason(self, score: float) -> str:
        """Get human-readable reason for match status."""
        if score >= 0.95:
            return "Exact match found in database"
        elif score >= 0.85:
            return "High-confidence match (possible typo correction)"
        elif score >= 0.75:
            return "Moderate match - review suggested address"
        elif score >= 0.5:
            return "Low confidence - similar addresses found but no strong match"
        else:
            return "No matching address found in database"

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        """Extract JSON from Nova response text."""
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
