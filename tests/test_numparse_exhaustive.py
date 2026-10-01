"""Exhaustive canonical, boundary, invariant, and fuzz tests for numparse."""

import random
import pytest
from voice_calculator.numparse import ParseResult, ParseStatus, RejectReason, parse


_UNITS = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]

_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]

_TEEN_PREFIXES = {
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
}


def canonical_words_for(n: int) -> str:
    """Generates canonical spoken English representation for an integer 0..2000."""
    if n < 0 or n > 2000:
        raise ValueError(f"Out of supported test generator range: {n}")

    if n < 20:
        return _UNITS[n]

    if n < 100:
        tens_part = _TENS[n // 10]
        rem = n % 10
        return tens_part if rem == 0 else f"{tens_part} {_UNITS[rem]}"

    if n < 1000:
        hundreds_digit = n // 100
        rem = n % 100
        base = f"{_UNITS[hundreds_digit]} hundred"
        if rem == 0:
            return base
        return f"{base} and {canonical_words_for(rem)}"

    if n < 2000:
        rem = n % 1000
        base = "one thousand"
        if rem == 0:
            return base
        if rem < 100:
            return f"{base} and {canonical_words_for(rem)}"
        return f"{base} {canonical_words_for(rem)}"

    return "two thousand"


def test_exhaustive_canonical_0_to_2000():
    """Verify that all 2,001 integers from 0 to 2000 round-trip from canonical spoken words."""
    for n in range(2001):
        words = canonical_words_for(n)
        res = parse(words)
        assert res.status == ParseStatus.SUCCESS, f"Failed on n={n} ('{words}'): {res.reason}"
        assert res.value == n, f"Expected {n}, got {res.value} for '{words}'"
        assert res.reason is None


def test_exhaustive_canonical_digits_0_to_2000():
    """Verify that all 2,001 integers from 0 to 2000 parse from canonical decimal strings."""
    for n in range(2001):
        digit_str = str(n)
        res = parse(digit_str)
        assert res.status == ParseStatus.SUCCESS, f"Failed on digit '{digit_str}': {res.reason}"
        assert res.value == n
        assert res.reason is None


def test_exhaustive_hyphenated_compound_tens():
    """Verify that all compound tens 21..99 with hyphens parse accurately."""
    for tens in range(20, 100, 10):
        for unit in range(1, 10):
            val = tens + unit
            phrase = f"{_TENS[tens // 10]}-{_UNITS[unit]}"
            res = parse(phrase)
            assert res.status == ParseStatus.SUCCESS, f"Failed on hyphenated '{phrase}': {res.reason}"
            assert res.value == val


def test_exhaustive_teen_hundreds_1100_to_1999():
    """Verify that all teen-hundred variants (1100..1999) parse accurately."""
    for teen_val in range(11, 20):
        prefix = _TEEN_PREFIXES[teen_val]
        # Base 1100, 1200, ..., 1900
        base_val = teen_val * 100
        base_phrase = f"{prefix} hundred"
        res = parse(base_phrase)
        assert res.status == ParseStatus.SUCCESS, f"Failed on '{base_phrase}': {res.reason}"
        assert res.value == base_val

        # Sample remainders 1..99 with and without "and"
        for rem in (1, 5, 15, 20, 50, 75, 99):
            val = base_val + rem
            rem_words = canonical_words_for(rem)
            # With "and"
            res_and = parse(f"{base_phrase} and {rem_words}")
            assert res_and.status == ParseStatus.SUCCESS, f"Failed on '{base_phrase} and {rem_words}': {res_and.reason}"
            assert res_and.value == val
            # Without "and"
            res_no_and = parse(f"{base_phrase} {rem_words}")
            assert res_no_and.status == ParseStatus.SUCCESS, f"Failed on '{base_phrase} {rem_words}': {res_no_and.reason}"
            assert res_no_and.value == val


def test_boundary_values():
    """Explicitly verify critical boundary values around 0, 100, 1000, 2000, and 2001."""
    boundaries = [
        ("zero", 0),
        ("one", 1),
        ("nineteen", 19),
        ("twenty", 20),
        ("twenty-one", 21),
        ("ninety-nine", 99),
        ("one hundred", 100),
        ("a hundred", 100),
        ("one hundred one", 101),
        ("one hundred and one", 101),
        ("a hundred and one", 101),
        ("one hundred ten", 110),
        ("one hundred and ten", 110),
        ("one hundred fifteen", 115),
        ("one hundred and fifteen", 115),
        ("nine hundred ninety-nine", 999),
        ("nine hundred and ninety-nine", 999),
        ("one thousand", 1000),
        ("a thousand", 1000),
        ("one thousand one", 1001),
        ("one thousand and one", 1001),
        ("a thousand and one", 1001),
        ("eleven hundred", 1100),
        ("one thousand one hundred", 1100),
        ("a thousand one hundred", 1100),
        ("one thousand one hundred and one", 1101),
        ("fifteen hundred", 1500),
        ("one thousand five hundred", 1500),
        ("nineteen hundred", 1900),
        ("nineteen hundred ninety-nine", 1999),
        ("one thousand nine hundred ninety-nine", 1999),
        ("two thousand", 2000),
    ]

    for phrase, expected in boundaries:
        res = parse(phrase)
        assert res.status == ParseStatus.SUCCESS, f"Boundary '{phrase}' failed: {res.reason}"
        assert res.value == expected

    # Boundary out of range
    out_boundaries = [
        "two thousand and one",
        "two thousand one",
        "two thousand and two",
        "two thousand five hundred",
        "twenty-one hundred",
        "twenty one hundred",
        "2001",
        "2002",
        "3000",
    ]
    for phrase in out_boundaries:
        res = parse(phrase)
        assert res.status == ParseStatus.REJECTED
        assert res.reason == RejectReason.OUT_OF_RANGE


def test_parser_invariants():
    """Verify general mathematical and contract invariants for any parse result."""
    test_inputs = [
        "zero",
        "forty-five",
        "one hundred and fifty",
        "two thousand",
        "invalid words here",
        "100",
        "2001",
        "",
        "   ",
        "-5",
        "fifteen hundred",
    ]

    for s in test_inputs:
        res = parse(s)
        assert isinstance(res, ParseResult)
        if res.status == ParseStatus.SUCCESS:
            assert res.value is not None
            assert 0 <= res.value <= 2000
            assert res.reason is None
            assert res.normalized_text != ""
        else:
            assert res.value is None
            assert res.reason is not None
            assert isinstance(res.reason, RejectReason)


def test_normalization_determinism():
    """Verify normalization preserves semantic evaluation regardless of casing, spacing, and trailing punctuation."""
    test_cases = [
        ("forty-five", 45),
        ("Forty Five", 45),
        ("  forty   five.  ", 45),
        ("FORTY FIVE?", 45),
        ("forty-five!", 45),
        ("one thousand two hundred and fifty", 1250),
        ("ONE THOUSAND TWO HUNDRED AND FIFTY.", 1250),
    ]
    for phrase, expected in test_cases:
        res = parse(phrase)
        assert res.status == ParseStatus.SUCCESS
        assert res.value == expected


def test_deterministic_adversarial_strings():
    """Verify that structured adversarial strings return expected rejections and never raise unhandled exceptions."""
    adversarial_inputs = [
        # Repeated punctuation / symbols
        ("!@#$%^&*()", RejectReason.MALFORMED),
        (":;\"'{}", RejectReason.MALFORMED),
        ("---", RejectReason.MALFORMED),
        ("- - -", RejectReason.MALFORMED),
        ("...", RejectReason.UNSUPPORTED),
        ("...!", RejectReason.UNSUPPORTED),
        # Repeated scale words
        ("hundred hundred hundred", RejectReason.MALFORMED),
        ("thousand thousand thousand", RejectReason.MALFORMED),
        ("a a a", RejectReason.MALFORMED),
        ("a hundred hundred", RejectReason.MALFORMED),
        ("a thousand thousand", RejectReason.MALFORMED),
        # Extreme whitespace & control characters
        ("   \t\t\n\r   ", RejectReason.EMPTY),
        ("one\x00thousand", RejectReason.MALFORMED),
        # Unicode characters
        ("一百", RejectReason.MALFORMED),
        ("deux", RejectReason.NOT_A_NUMBER),
        ("hundert", RejectReason.NOT_A_NUMBER),
        ("123\u0660", RejectReason.MALFORMED),
        ("\u200b", RejectReason.MALFORMED),
        # Very long repetitive strings
        ("one " * 500, RejectReason.MULTIPLE_NUMBERS),
        ("thousand " * 200, RejectReason.MALFORMED),
        ("9" * 300, RejectReason.OUT_OF_RANGE),
    ]

    for phrase, expected_reason in adversarial_inputs:
        res = parse(phrase)
        assert isinstance(res, ParseResult)
        assert res.status == ParseStatus.REJECTED, f"Expected reject for '{phrase}', got {res.value}"
        assert res.value is None
        assert res.reason == expected_reason, f"For '{phrase}', expected {expected_reason} but got {res.reason}"


def test_non_string_inputs():
    """Verify that non-string inputs fail safely without unhandled exceptions."""
    non_strings = [None, 123, 45.6, [], {}, True, False]
    for val in non_strings:
        res = parse(val)  # type: ignore
        assert isinstance(res, ParseResult)
        assert res.status == ParseStatus.REJECTED
        assert res.value is None
        assert res.reason == RejectReason.MALFORMED


def test_fuzz_arbitrary_random_tokens():
    """Verify that arbitrary random token permutations never raise exceptions."""
    vocabulary = [
        "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
        "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "twenty", "thirty",
        "hundred", "thousand", "and", "a", "random", "word", "50", "007", "15.0", "-", "!", ""
    ]

    rng = random.Random(42)  # Deterministic seed

    for _ in range(500):
        length = rng.randint(0, 8)
        sample_tokens = [rng.choice(vocabulary) for _ in range(length)]
        phrase = " ".join(sample_tokens)

        # Must not raise an exception
        res = parse(phrase)
        assert isinstance(res, ParseResult)
        if res.status == ParseStatus.SUCCESS:
            assert 0 <= res.value <= 2000
            assert res.reason is None
        else:
            assert res.value is None
            assert res.reason is not None
