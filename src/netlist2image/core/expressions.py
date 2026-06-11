"""Recursive-descent parser for SPICE parameter expressions."""

from __future__ import annotations

import re
from typing import Optional

# Common SPICE unit suffixes and their multipliers
UNIT_MULTIPLIERS = {
    "T": 1e12,
    "G": 1e9,
    "MEG": 1e6,
    "X": 1e6,  # LTspice sometimes uses X for MEG
    "K": 1e3,
    "M": 1e-3,
    "MI": 1e-3,  # some dialects use MI for milli
    "U": 1e-6,
    "N": 1e-9,
    "P": 1e-12,
    "F": 1e-15,
    # Unit-only suffixes (no multiplier, just the unit)
    "V": 1,
    "A": 1,
    "H": 1,
    "OHM": 1,
    "Ω": 1,
}

# Regex to match a number with optional unit suffix
_NUMBER_WITH_UNIT_RE = re.compile(
    r"^\s*([+-]?\d+\.?\d*[eE][+-]?\d+|[+-]?\d+\.\d*|[+-]?\d+)\s*(T|MEG|MI|X|G|K|M|U|N|P|F|V|A|H|OHM|Ω)?\s*$",
    re.IGNORECASE,
)


def parse_numeric_value(raw: str) -> Optional[float]:
    """Parse a SPICE numeric value with unit suffix.

    Returns None if the value cannot be parsed as a simple numeric.
    """
    raw = raw.strip()
    if not raw:
        return None

    match = _NUMBER_WITH_UNIT_RE.match(raw)
    if not match:
        return None

    num_str = match.group(1)
    unit_str = match.group(2)

    try:
        value = float(num_str)
    except ValueError:
        return None

    if unit_str:
        multiplier = UNIT_MULTIPLIERS.get(unit_str.upper())
        if multiplier is not None:
            value *= multiplier

    return value


def parse_unit(raw: str) -> Optional[str]:
    """Extract the unit suffix from a SPICE value string."""
    raw = raw.strip()
    match = _NUMBER_WITH_UNIT_RE.match(raw)
    if match and match.group(2):
        return match.group(2).upper()
    return None
