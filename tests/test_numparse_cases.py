"""Comprehensive test cases for deterministic English number parsing."""

import pytest
from voice_calculator.numparse import ParseResult, ParseStatus, RejectReason, parse


# --- 1. Documented Accepted Cases ---


@pytest.mark.parametrize(
    "phrase, expected_val",
    [
        # Zero
        ("zero", 0),
        # Units and teens
        ("one", 1),
        ("two", 2),
        ("three", 3),
        ("four", 4),
        ("five", 5),
        ("six", 6),
        ("seven", 7),
        ("eight", 8),
        ("nine", 9),
        ("ten", 10),
        ("eleven", 11),
        ("twelve", 12),
        ("thirteen", 13),
        ("fourteen", 14),
        ("fifteen", 15),
        ("sixteen", 16),
        ("seventeen", 17),
        ("eighteen", 18),
        ("nineteen", 19),
        # Tens
        ("twenty", 20),
        ("thirty", 30),
        ("forty", 40),
        ("fifty", 50),
        ("sixty", 60),
        ("seventy", 70),
        ("eighty", 80),
        ("ninety", 90),
        # Compound tens
        ("twenty one", 21),
        ("twenty-one", 21),
        ("forty five", 45),
        ("forty-five", 45),
        ("ninety nine", 99),
        ("ninety-nine", 99),
        # Hundreds (with one and a)
        ("one hundred", 100),
        ("a hundred", 100),
        ("one hundred five", 105),
        ("one hundred and five", 105),
        ("a hundred five", 105),
        ("a hundred and five", 105),
        ("one hundred fifty", 150),
        ("one hundred and fifty", 150),
        ("two hundred fifty", 250),
        ("two hundred and fifty", 250),
        ("two hundred and five", 205),
        ("nine hundred ninety-nine", 999),
        ("nine hundred and ninety-nine", 999),
        # Teen hundreds (1100-1999)
        ("eleven hundred", 1100),
        ("twelve hundred", 1200),
        ("fifteen hundred", 1500),
        ("fifteen hundred fifty", 1550),
        ("fifteen hundred and fifty", 1550),
        ("sixteen hundred", 1600),
        ("nineteen hundred", 1900),
        ("nineteen hundred ninety-nine", 1999),
        # Thousands
        ("one thousand", 1000),
        ("a thousand", 1000),
        ("one thousand five", 1005),
        ("one thousand and five", 1005),
        ("a thousand five", 1005),
        ("a thousand and five", 1005),
        ("one thousand fifty", 1050),
        ("one thousand and fifty", 1050),
        ("one thousand two hundred", 1200),
        ("one thousand and two hundred", 1200),
        ("a thousand two hundred", 1200),
        ("one thousand two hundred five", 1205),
        ("one thousand two hundred and five", 1205),
        ("one thousand and two hundred and five", 1205),
        ("one thousand two hundred fifty", 1250),
        ("one thousand two hundred and fifty", 1250),
        ("a thousand two hundred and fifty", 1250),
        ("one thousand five hundred", 1500),
        ("one thousand and five hundred", 1500),
        ("one thousand nine hundred ninety-nine", 1999),
        ("one thousand and nine hundred and ninety-nine", 1999),
        # Upper bound 2000
        ("two thousand", 2000),
        # Canonical ASCII digit strings
        ("0", 0),
        ("1", 1),
        ("45", 45),
        ("100", 100),
        ("1500", 1500),
        ("2000", 2000),
        # Harmless sentence-final punctuation
        ("forty five.", 45),
        ("forty five?", 45),
        ("forty five!", 45),
        ("  one hundred  ", 100),
        # Mixed case
        ("ONE HUNDRED", 100),
        ("Forty-Five", 45),
        ("Two Thousand", 2000),
    ],
)
def test_accepted_cases(phrase: str, expected_val: int):
    res = parse(phrase)
    assert res.status == ParseStatus.SUCCESS, f"Failed on '{phrase}': {res.reason}"
    assert res.value == expected_val
    assert res.reason is None


# --- 2. Documented Rejected Cases by Reason Code ---


@pytest.mark.parametrize(
    "phrase, expected_reason",
    [
        # EMPTY
        ("", RejectReason.EMPTY),
        ("   ", RejectReason.EMPTY),
        (" \t \n ", RejectReason.EMPTY),
        # NOT_A_NUMBER
        ("hello", RejectReason.NOT_A_NUMBER),
        ("undo", RejectReason.NOT_A_NUMBER),
        ("stop", RejectReason.NOT_A_NUMBER),
        ("yes", RejectReason.NOT_A_NUMBER),
        ("no", RejectReason.NOT_A_NUMBER),
        ("um", RejectReason.NOT_A_NUMBER),
        ("start", RejectReason.NOT_A_NUMBER),
        ("total", RejectReason.NOT_A_NUMBER),
        ("clear", RejectReason.NOT_A_NUMBER),
        ("dollars", RejectReason.NOT_A_NUMBER),
        ("rupees", RejectReason.NOT_A_NUMBER),
        ("cents", RejectReason.NOT_A_NUMBER),
        ("paise", RejectReason.NOT_A_NUMBER),
        ("apple", RejectReason.NOT_A_NUMBER),
        # OUT_OF_RANGE (>2000)
        ("two thousand and one", RejectReason.OUT_OF_RANGE),
        ("two thousand one", RejectReason.OUT_OF_RANGE),
        ("two thousand five hundred", RejectReason.OUT_OF_RANGE),
        ("twenty five hundred", RejectReason.OUT_OF_RANGE),
        ("twenty-five hundred", RejectReason.OUT_OF_RANGE),
        ("three thousand", RejectReason.OUT_OF_RANGE),
        ("five thousand", RejectReason.OUT_OF_RANGE),
        ("2001", RejectReason.OUT_OF_RANGE),
        ("2500", RejectReason.OUT_OF_RANGE),
        ("5000", RejectReason.OUT_OF_RANGE),
        # UNSUPPORTED (negatives, decimals, fractions, foreign units)
        ("minus five", RejectReason.UNSUPPORTED),
        ("negative ten", RejectReason.UNSUPPORTED),
        ("-5", RejectReason.UNSUPPORTED),
        ("+50", RejectReason.UNSUPPORTED),
        ("three point five", RejectReason.UNSUPPORTED),
        ("15.0", RejectReason.UNSUPPORTED),
        ("half", RejectReason.UNSUPPORTED),
        ("one fourth", RejectReason.UNSUPPORTED),
        ("lakh", RejectReason.UNSUPPORTED),
        ("crore", RejectReason.UNSUPPORTED),
        # MALFORMED (structural errors)
        ("hundred", RejectReason.MALFORMED),
        ("hundred fifty", RejectReason.MALFORMED),
        ("thousand", RejectReason.MALFORMED),
        ("ten hundred", RejectReason.MALFORMED),
        ("twenty hundred", RejectReason.MALFORMED),
        ("fifty hundred", RejectReason.MALFORMED),
        ("five hundred hundred", RejectReason.MALFORMED),
        ("thousand thousand", RejectReason.MALFORMED),
        ("one thousand thousand", RejectReason.MALFORMED),
        ("hundred and", RejectReason.MALFORMED),
        ("and fifty", RejectReason.MALFORMED),
        ("forty and five", RejectReason.MALFORMED),
        ("one thousand fifteen hundred", RejectReason.MALFORMED),
        ("a five", RejectReason.MALFORMED),
        ("a twenty", RejectReason.MALFORMED),
        ("007", RejectReason.MALFORMED),
        ("05", RejectReason.MALFORMED),
        ("1,500", RejectReason.MALFORMED),
        ("1-500", RejectReason.MALFORMED),
        ("٤٥", RejectReason.MALFORMED),
        # AMBIGUOUS (compound / year style / missing scale)
        ("twenty twenty", RejectReason.AMBIGUOUS),
        ("fifteen fifty", RejectReason.AMBIGUOUS),
        ("thirteen fifty", RejectReason.AMBIGUOUS),
        ("one twenty", RejectReason.AMBIGUOUS),
        # MULTIPLE_NUMBERS (digit-by-digit or disconnected numbers)
        ("one two three", RejectReason.MULTIPLE_NUMBERS),
        ("four five", RejectReason.MULTIPLE_NUMBERS),
        ("zero zero", RejectReason.MULTIPLE_NUMBERS),
        ("forty five fifty", RejectReason.MULTIPLE_NUMBERS),
        ("one hundred two hundred", RejectReason.MULTIPLE_NUMBERS),
    ],
)
def test_rejected_cases(phrase: str, expected_reason: RejectReason):
    res = parse(phrase)
    assert res.status == ParseStatus.REJECTED, f"Expected reject for '{phrase}' but got {res.value}"
    assert res.value is None
    assert res.reason == expected_reason, f"For '{phrase}', expected {expected_reason} but got {res.reason}"
