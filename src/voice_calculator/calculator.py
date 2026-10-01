"""Deterministic calculation core, history, undo, and reset.

Maintains:
- Running total of accepted numerical additions.
- Ordered, immutable history of accepted addition entries.
- Reversible undo operation (LIFO removal of the latest addition).
- State reset / clear operation.

Safety Invariants:
- Total is always strictly derived from / consistent with accepted history entries.
- Rejects non-integer, negative, or out-of-range (>2000) values with typed exceptions.
- Zero floating-point arithmetic.
- Pure domain component: zero dependencies on audio, ASR, VAD, GUI, or speech parsing.
- Safe on empty history (undo on empty history is a safe no-op returning None).
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import time
from typing import Optional, Tuple

from voice_calculator.config import MAX_NUMBER, MIN_NUMBER

logger = logging.getLogger("voice_calculator.calculator")


class CalculatorError(Exception):
    """Base exception for calculator domain errors."""


class InvalidValueError(CalculatorError):
    """Raised when an attempt is made to add an invalid, negative, non-integer, or out-of-range value."""


@dataclass(frozen=True)
class HistoryEntry:
    """Immutable record of a single accepted addition.

    Attributes:
        sequence: 1-indexed sequential addition number.
        value: Accepted integer added (0–2000).
        running_total: Resulting running total immediately after this addition.
        timestamp: Monotonic or POSIX epoch timestamp of addition.
        timestamp_iso: Optional ISO 8601 UTC timestamp string for display/audit.
    """

    sequence: int
    value: int
    running_total: int
    timestamp: float
    timestamp_iso: str


class Calculator:
    """Deterministic accumulator with history tracking, undo, and reset operations."""

    def __init__(
        self,
        min_number: int = MIN_NUMBER,
        max_number: int = MAX_NUMBER,
    ) -> None:
        self.min_number = min_number
        self.max_number = max_number
        self._entries: list[HistoryEntry] = []

    @property
    def total(self) -> int:
        """Current running total, strictly derived from active history entries."""
        return sum(entry.value for entry in self._entries)

    @property
    def history(self) -> Tuple[HistoryEntry, ...]:
        """Immutable tuple of all accepted addition entries in chronological order."""
        return tuple(self._entries)

    @property
    def count(self) -> int:
        """Total number of active additions in history."""
        return len(self._entries)

    @property
    def is_empty(self) -> bool:
        """True if no additions have been made (or all have been undone/cleared)."""
        return len(self._entries) == 0

    @property
    def last_entry(self) -> Optional[HistoryEntry]:
        """Most recent addition entry, or None if history is empty."""
        if self._entries:
            return self._entries[-1]
        return None

    def add(
        self,
        value: int,
        timestamp: Optional[float] = None,
    ) -> HistoryEntry:
        """Adds an accepted integer to the running total and records a history entry.

        Args:
            value: Integer within [min_number, max_number] (default 0–2000).
            timestamp: Optional epoch timestamp. If None, current time is used.

        Returns:
            The created immutable HistoryEntry.

        Raises:
            InvalidValueError: If value is not an int (or is a bool), or is outside [min_number, max_number].
        """
        # Strict type validation (reject floats, bools, strings, None)
        if not isinstance(value, int) or isinstance(value, bool):
            raise InvalidValueError(
                f"Calculator value must be an integer, got {type(value).__name__}: {value!r}"
            )

        # Strict numerical range validation
        if not (self.min_number <= value <= self.max_number):
            raise InvalidValueError(
                f"Value {value} is outside allowed calculator range {self.min_number}–{self.max_number}."
            )

        ts = timestamp if timestamp is not None else time.time()
        iso_str = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

        seq = len(self._entries) + 1
        new_total = self.total + value

        entry = HistoryEntry(
            sequence=seq,
            value=value,
            running_total=new_total,
            timestamp=ts,
            timestamp_iso=iso_str,
        )

        self._entries.append(entry)
        logger.debug("Calculator added %d (sequence=%d, total=%d)", value, seq, new_total)
        return entry

    def undo(self) -> Optional[HistoryEntry]:
        """Removes the most recent accepted addition and restores the previous total.

        Returns:
            The removed HistoryEntry, or None if history was empty.
        """
        if not self._entries:
            logger.debug("Undo called on empty calculator history; no-op.")
            return None

        removed = self._entries.pop()
        logger.debug(
            "Calculator undone entry sequence=%d, value=%d (restored total=%d)",
            removed.sequence,
            removed.value,
            self.total,
        )
        return removed

    def reset(self) -> None:
        """Clears all history entries and resets the running total to 0."""
        self._entries.clear()
        logger.debug("Calculator reset: total=0, history cleared.")

    def clear(self) -> None:
        """Alias for reset()."""
        self.reset()
