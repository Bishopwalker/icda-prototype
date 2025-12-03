import re
from dataclasses import dataclass


@dataclass
class GuardrailFlags:
    pii: bool = True
    financial: bool = True
    credentials: bool = True
    offtopic: bool = True


class Guardrails:
    __slots__ = ()

    # Pattern name, regex, message
    _RULES = [
        ("pii", r"\b(ssn|social\s*security)\b", "SSN not accessible"),
        ("financial", r"\b(credit\s*card|bank\s*account)\b", "Financial info not accessible"),
        ("credentials", r"\b(password|secret|token)\b", "Credentials not accessible"),
        ("offtopic", r"\b(weather|poem|story|joke)\b", "I only help with customer data queries"),
    ]

    _PATTERNS = {name: (re.compile(pattern, re.I), msg) for name, pattern, msg in _RULES}

    @classmethod
    def check(cls, query: str, flags: GuardrailFlags | None = None) -> str | None:
        if flags is None:
            flags = GuardrailFlags()

        for name, (pattern, msg) in cls._PATTERNS.items():
            if getattr(flags, name, True) and pattern.search(query):
                return msg
        return None
