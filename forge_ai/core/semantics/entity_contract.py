"""Canonical Entity Synthesis structural contract.

This module contains only provider-independent structural limits. Product-side
sanitizers may be more permissive for robustness, but model capability evidence
must use these stricter limits. Backend adapters import these values rather than
re-declaring a parallel contract.
"""

from __future__ import annotations

ENTITY_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
ENTITY_STRICT_MIN_FIELDS = 1
ENTITY_STRICT_MAX_FIELDS = 6
ENTITY_STRICT_MIN_CHOICES = 2
ENTITY_STRICT_MAX_CHOICES = 6

__all__ = [
    "ENTITY_IDENTIFIER_PATTERN",
    "ENTITY_STRICT_MIN_FIELDS",
    "ENTITY_STRICT_MAX_FIELDS",
    "ENTITY_STRICT_MIN_CHOICES",
    "ENTITY_STRICT_MAX_CHOICES",
]
