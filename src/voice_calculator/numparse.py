"""Deterministic English number parser for Voice Calculator.

Supports:
- Spoken English number expressions from 0 to 2000.
- Canonical ASCII digit strings from 0 to 2000.

Guarantees:
- Pure, deterministic, no I/O, no network, no LLM/ASR dependencies.
- Never raises unhandled exceptions on arbitrary input strings.
- Never silently guesses the user's intended number.
- Rejection always includes an explicit RejectReason.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class ParseStatus(Enum):
    """Outcome status of the parse operation."""

    SUCCESS = "SUCCESS"
    REJECTED = "REJECTED"


class RejectReason(Enum):
    """Explicit reason codes for rejected inputs."""

    EMPTY = "EMPTY"
    NOT_A_NUMBER = "NOT_A_NUMBER"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNSUPPORTED = "UNSUPPORTED"
    MALFORMED = "MALFORMED"
    AMBIGUOUS = "AMBIGUOUS"
    MULTIPLE_NUMBERS = "MULTIPLE_NUMBERS"


@dataclass(frozen=True)
class ParseResult:
    """Immutable result of parsing a number string."""

    status: ParseStatus
    value: Optional[int] = None
    reason: Optional[RejectReason] = None
    normalized_text: str = ""


# --- Closed Vocabulary Definitions ---

_UNITS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
}

_TEENS = {
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

# Teen multipliers valid for "teen hundred" (1100-1900)
_TEEN_HUNDRED_MULTIPLIERS = {
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}

_TENS = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_UNSUPPORTED_KEYWORDS = {
    "minus",
    "negative",
    "plus",
    "point",
    "dot",
    "half",
    "fourth",
    "quarter",
    "lakh",
    "crore",
    "million",
    "billion",
    "trillion",
}

_KNOWN_WORDS = (
    set(_UNITS.keys())
    | set(_TEENS.keys())
    | set(_TENS.keys())
    | {"zero", "a", "hundred", "thousand", "and"}
    | _UNSUPPORTED_KEYWORDS
)


def _success(value: int, normalized: str) -> ParseResult:
    """Constructs a successful ParseResult."""
    return ParseResult(
        status=ParseStatus.SUCCESS,
        value=value,
        reason=None,
        normalized_text=normalized,
    )


def _reject(reason: RejectReason, normalized: str = "") -> ParseResult:
    """Constructs a rejected ParseResult."""
    return ParseResult(
        status=ParseStatus.REJECTED,
        value=None,
        reason=reason,
        normalized_text=normalized,
    )


def _normalize_raw_input(text: str) -> Tuple[Optional[str], Optional[RejectReason]]:
    """Performs raw string inspection and normalization.

    Returns:
        Tuple of (normalized_string, error_reason). If error_reason is not None,
        normalization failed immediately.
    """
    if not isinstance(text, str):
        return None, RejectReason.MALFORMED

    stripped = text.strip()
    if not stripped:
        return None, RejectReason.EMPTY

    # Reject unsupported prefix operators on numbers (e.g. "+50", "-5")
    if stripped.startswith(("+", "-")):
        if any(c.isalnum() for c in stripped):
            return None, RejectReason.UNSUPPORTED
        return None, RejectReason.MALFORMED

    # Check for internal decimals or commas
    if "." in stripped[:-1]:
        return None, RejectReason.UNSUPPORTED
    if "," in stripped:
        return None, RejectReason.MALFORMED

    # Reject hyphens adjacent to digits (e.g. "1-500", "5-") as MALFORMED
    for i, ch in enumerate(stripped):
        if ch == "-":
            if (i > 0 and stripped[i - 1].isdigit()) or (i + 1 < len(stripped) and stripped[i + 1].isdigit()):
                return None, RejectReason.MALFORMED

    # Strip sentence-final punctuation (. ? !)
    if stripped.endswith((".", "?", "!")):
        stripped = stripped[:-1].rstrip()
        if not stripped:
            return None, RejectReason.EMPTY

    # Reject if any remaining punctuation (except internal hyphens) or non-ASCII characters
    for ch in stripped:
        if ord(ch) > 127:
            return None, RejectReason.MALFORMED
        if not (ch.isalnum() or ch in (" ", "-")):
            return None, RejectReason.MALFORMED

    # Case normalization & hyphen normalization
    lowered = stripped.lower()
    hyphen_normalized = lowered.replace("-", " ")
    collapsed = " ".join(hyphen_normalized.split())

    if not collapsed:
        return None, RejectReason.EMPTY

    return collapsed, None


def _parse_digit_string(text: str) -> Optional[ParseResult]:
    """Parses pure ASCII digit strings."""
    if not text.isdigit():
        return None

    # Check for non-canonical leading zeros (e.g. "007", "05")
    if text.startswith("0") and len(text) > 1:
        return _reject(RejectReason.MALFORMED, text)

    try:
        val = int(text)
    except ValueError:
        return _reject(RejectReason.MALFORMED, text)

    if 0 <= val <= 2000:
        return _success(val, text)
    else:
        return _reject(RejectReason.OUT_OF_RANGE, text)


def _parse_below100(tokens: List[str], start: int) -> Tuple[Optional[int], int, Optional[RejectReason]]:
    """Parses a sub-100 number expression (1..99).

    Returns:
        (value, next_index, reject_reason)
    """
    if start >= len(tokens):
        return None, start, None

    token = tokens[start]

    # Unit 1..9
    if token in _UNITS:
        return _UNITS[token], start + 1, None

    # Teen 10..19
    if token in _TEENS:
        return _TEENS[token], start + 1, None

    # Tens 20..90
    if token in _TENS:
        tens_val = _TENS[token]
        # Check compound tens: tens + unit (e.g., twenty five)
        if start + 1 < len(tokens) and tokens[start + 1] in _UNITS:
            unit_val = _UNITS[tokens[start + 1]]
            return tens_val + unit_val, start + 2, None
        return tens_val, start + 1, None

    return None, start, None


def _parse_tokens(tokens: List[str], normalized: str) -> ParseResult:
    """Evaluates validated word tokens against the formal English number grammar."""
    n = len(tokens)
    if n == 0:
        return _reject(RejectReason.EMPTY, normalized)

    # Check for unsupported explicit keywords
    for token in tokens:
        if token in _UNSUPPORTED_KEYWORDS:
            return _reject(RejectReason.UNSUPPORTED, normalized)

    # Check for unrecognized vocabulary
    for token in tokens:
        if token not in _KNOWN_WORDS:
            return _reject(RejectReason.NOT_A_NUMBER, normalized)

    # Standalone zero
    if tokens == ["zero"]:
        return _success(0, normalized)

    # "zero" used in compound/multi-digit phrase
    if "zero" in tokens:
        if n > 1 and all(t in _UNITS or t == "zero" for t in tokens):
            return _reject(RejectReason.MULTIPLE_NUMBERS, normalized)
        return _reject(RejectReason.MALFORMED, normalized)

    # Check for dangling or misplaced "and"
    if tokens[0] == "and" or tokens[-1] == "and":
        return _reject(RejectReason.MALFORMED, normalized)

    # Check for "a" preceding non-scale words (e.g. "a five", "a twenty")
    for i, t in enumerate(tokens):
        if t == "a":
            if i + 1 >= n or tokens[i + 1] not in ("hundred", "thousand"):
                return _reject(RejectReason.MALFORMED, normalized)

    # Check for digit-by-digit sequences (e.g. "one two three", "four five")
    if n >= 2 and all(t in _UNITS for t in tokens):
        return _reject(RejectReason.MULTIPLE_NUMBERS, normalized)

    # Check for year-style / ambiguous compounds
    # e.g., "twenty twenty", "fifteen fifty", "thirteen fifty"
    if n == 2:
        t0, t1 = tokens[0], tokens[1]
        if (t0 in _TENS and t1 in _TENS) or (t0 in _TEENS and t1 in _TENS):
            return _reject(RejectReason.AMBIGUOUS, normalized)
        if t0 in _UNITS and t1 in _TENS:
            return _reject(RejectReason.AMBIGUOUS, normalized)

    # Check for malformed scale patterns
    for i in range(n - 1):
        if tokens[i] == "hundred" and tokens[i + 1] == "hundred":
            return _reject(RejectReason.MALFORMED, normalized)
        if tokens[i] == "thousand" and tokens[i + 1] == "thousand":
            return _reject(RejectReason.MALFORMED, normalized)

    # Check invalid scale multipliers: "ten hundred", "twenty hundred", "fifty hundred"
    if "hundred" in tokens:
        h_idx = tokens.index("hundred")
        if h_idx > 0:
            prev = tokens[h_idx - 1]
            if prev == "ten" or prev in _TENS:
                # Check "twenty five hundred" -> 2500 (grammatically valid number out of range)
                if h_idx == 2 and tokens[0] in _TENS and tokens[1] in _UNITS:
                    pass  # compound tens before hundred e.g. "twenty five hundred" -> OUT_OF_RANGE
                else:
                    return _reject(RejectReason.MALFORMED, normalized)

    # Check "one thousand fifteen hundred" (thousand combined with teen-hundred)
    if "thousand" in tokens and "hundred" in tokens:
        th_idx = tokens.index("thousand")
        h_idx = tokens.index("hundred")
        if h_idx > th_idx:
            # Check word immediately before hundred
            if tokens[h_idx - 1] in _TEEN_HUNDRED_MULTIPLIERS and tokens[h_idx - 1] != "one":
                return _reject(RejectReason.MALFORMED, normalized)

    # --- Parse Grammar Structure ---
    # Grammar hierarchy:
    # 1. Thousand clause (optional)
    # 2. Hundred clause (optional)
    # 3. Sub-100 remainder clause (optional)

    idx = 0
    total_val = 0

    # 1. Thousand Clause
    if idx < n and tokens[idx] == "thousand":
        total_val += 1000
        idx += 1

        # Optional connective "and" after thousand
        if idx < n and tokens[idx] == "and":
            idx += 1
            if idx >= n:
                return _reject(RejectReason.MALFORMED, normalized)
    elif idx < n and (tokens[idx] in _UNITS or tokens[idx] == "a") and idx + 1 < n and tokens[idx + 1] == "thousand":
        th_mult = 1 if tokens[idx] == "a" else _UNITS[tokens[idx]]
        total_val += th_mult * 1000
        idx += 2

        # Optional connective "and" after thousand
        if idx < n and tokens[idx] == "and":
            idx += 1
            if idx >= n:
                return _reject(RejectReason.MALFORMED, normalized)

    # 2. Hundred Clause
    if idx < n and "hundred" in tokens[idx:]:
        h_pos = tokens.index("hundred", idx)
        # Multiplier before hundred can be:
        # - Empty (bare "hundred" e.g. "hundred", "hundred and five", "hundred twenty five") -> multiplier 1
        # - "a" or unit (1..9) -> multiplier 1..9
        # - teen (11..19) for teen-hundreds
        # - compound tens (e.g. "twenty five" in "twenty five hundred" -> 2500)
        mult_tokens = tokens[idx:h_pos]

        h_mult = 0
        if not mult_tokens:
            h_mult = 1
        elif len(mult_tokens) == 1:
            m = mult_tokens[0]
            if m == "a":
                h_mult = 1
            elif m in _UNITS:
                h_mult = _UNITS[m]
            elif m in _TEEN_HUNDRED_MULTIPLIERS:
                h_mult = _TEEN_HUNDRED_MULTIPLIERS[m]
            else:
                return _reject(RejectReason.MALFORMED, normalized)
        elif len(mult_tokens) == 2 and mult_tokens[0] in _TENS and mult_tokens[1] in _UNITS:
            h_mult = _TENS[mult_tokens[0]] + _UNITS[mult_tokens[1]]
        else:
            return _reject(RejectReason.MALFORMED, normalized)

        total_val += h_mult * 100
        idx = h_pos + 1

        # Optional connective "and" after hundred
        if idx < n and tokens[idx] == "and":
            idx += 1
            if idx >= n:
                return _reject(RejectReason.MALFORMED, normalized)

    # 3. Sub-100 Remainder Clause
    if idx < n:
        # Prevent misplaced "and" between tens and units
        # e.g., "forty and five" -> tokens: ["forty", "and", "five"]
        if idx + 2 < n and tokens[idx] in _TENS and tokens[idx + 1] == "and" and tokens[idx + 2] in _UNITS:
            return _reject(RejectReason.MALFORMED, normalized)

        val_sub, next_idx, _ = _parse_below100(tokens, idx)
        if val_sub is not None and next_idx == n:
            total_val += val_sub
            idx = next_idx
        else:
            # Check if remaining tokens form another number (multiple numbers in utterance)
            if idx < n:
                if "hundred" in tokens[idx:] or "thousand" in tokens[idx:]:
                    return _reject(RejectReason.MULTIPLE_NUMBERS, normalized)
                val1, idx1, _ = _parse_below100(tokens, idx)
                if val1 is not None and idx1 < n:
                    val2, idx2, _ = _parse_below100(tokens, idx1)
                    if val2 is not None and idx2 == n:
                        return _reject(RejectReason.MULTIPLE_NUMBERS, normalized)
            return _reject(RejectReason.MALFORMED, normalized)

    if idx != n:
        return _reject(RejectReason.MALFORMED, normalized)

    # Final Range Validation (0..2000)
    if 0 <= total_val <= 2000:
        return _success(total_val, normalized)
    else:
        return _reject(RejectReason.OUT_OF_RANGE, normalized)


def parse(text: str) -> ParseResult:
    """Parses a recognized spoken English phrase or canonical digit string into an integer 0..2000.

    Args:
        text: Raw recognized text from ASR or user input.

    Returns:
        ParseResult containing status (SUCCESS/REJECTED), integer value on success,
        and explicit RejectReason on failure.
    """
    try:
        normalized, error_reason = _normalize_raw_input(text)
        if error_reason is not None:
            return _reject(error_reason, normalized or "")

        assert normalized is not None

        # Check pure digit string first
        digit_result = _parse_digit_string(normalized)
        if digit_result is not None:
            return digit_result

        # Check if digit string had internal formatting issues (e.g. "1-500", "007")
        # If tokens are digits mixed with spaces
        tokens = normalized.split()
        if any(t.isdigit() for t in tokens):
            if len(tokens) == 1:
                return _parse_digit_string(tokens[0]) or _reject(RejectReason.MALFORMED, normalized)
            if all(t.isdigit() for t in tokens):
                return _reject(RejectReason.MULTIPLE_NUMBERS, normalized)
            return _reject(RejectReason.MALFORMED, normalized)

        return _parse_tokens(tokens, normalized)

    except Exception:
        # Parser must never raise unhandled exceptions on arbitrary inputs
        return _reject(RejectReason.MALFORMED, text if isinstance(text, str) else "")
