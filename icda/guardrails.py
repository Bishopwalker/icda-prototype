import re


class Guardrails:
    __slots__ = ()

    _PATTERNS = tuple(
        (re.compile(p, re.I), msg) for p, msg in [
            (r"\b(ssn|social\s*security)\b", "SSN not accessible"),
            (r"\b(credit\s*card|bank\s*account)\b", "Financial info not accessible"),
            (r"\b(password|secret|token)\b", "Credentials not accessible"),
            (r"\b(weather|poem|story|joke)\b", "I only help with customer data queries"),
        ]
    )

    @classmethod
    def check(cls, query: str) -> str | None:
        for pattern, msg in cls._PATTERNS:
            if pattern.search(query):
                return msg
        return None
