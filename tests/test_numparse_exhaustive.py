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
        ("one hundred one", 101),
        ("one hundred and one", 101),
        ("one hundred ten", 110),
        ("one hundred and ten", 110),
        ("one hundred fifteen", 115),
        ("one hundred and fifteen", 115),
        ("nine hundred ninety-nine", 999),
        ("nine hundred and ninety-nine", 999),
        ("one thousand", 1000),
        ("one thousand one", 1001),
        ("one thousand and one", 1001),
        ("eleven hundred", 1100),
        ("one thousand one hundred", 1100),
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
        else:
            assert res.value is None
            assert res.reason is not None
            assert isinstance(res.reason, RejectReason)


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
