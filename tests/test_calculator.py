"""Unit and invariant tests for Calculator Core, History, Undo & Reset (Phase 3.5).

Verifies:
- Invariant 1: Initial total is zero.
- Invariant 2: Initial history is empty.
- Invariant 3: Valid addition updates total correctly.
- Invariant 4: Multiple additions preserve order and sequence.
- Invariant 5: Zero can be added and creates a valid history entry.
- Invariant 6: Undo removes exactly the latest addition.
- Invariant 7: Multiple undos work in reverse order (LIFO).
- Invariant 8: Undo on empty history is safe (returns None).
- Invariant 9: Clear/reset removes all history and returns total to zero.
- Invariant 10: Values outside 0–2000 are rejected (InvalidValueError).
- Invariant 11: Negative values are rejected.
- Invariant 12: Non-integer values are rejected (floats, strings, booleans, None).
- Invariant 13: Zero floating-point arithmetic (total is strictly int).
- Invariant 14: History and total remain internally consistent.
- Invariant 15: Calculator state is not corrupted by a failed operation.
- Invariant 16: Zero dependencies on audio, ASR, VAD, GUI, or parser code.
- Invariant 17: No raw speech text can be passed as arithmetic value.
- Invariant 18: HistoryEntry and history tuple are immutable.
"""

from dataclasses import FrozenInstanceError
import sys
import pytest

from voice_calculator.calculator import (
    Calculator,
    CalculatorError,
    HistoryEntry,
    InvalidValueError,
)


class TestCalculator:
    """Test suite for Calculator domain state."""

    def test_initial_state(self):
        """Initial calculator total is 0 and history is empty."""
        calc = Calculator()
        assert calc.total == 0
        assert isinstance(calc.total, int)
        assert calc.history == ()
        assert calc.count == 0
        assert calc.is_empty is True
        assert calc.last_entry is None

    def test_single_addition(self):
        """Adding a valid integer updates total and appends a history entry."""
        calc = Calculator()
        entry = calc.add(50)

        assert isinstance(entry, HistoryEntry)
        assert entry.sequence == 1
        assert entry.value == 50
        assert entry.running_total == 50
        assert calc.total == 50
        assert calc.count == 1
        assert calc.is_empty is False
        assert calc.last_entry == entry

    def test_multiple_additions_order_and_sum(self):
        """Multiple additions preserve strict chronological order and cumulative sums."""
        calc = Calculator()
        e1 = calc.add(50)
        e2 = calc.add(120)
        e3 = calc.add(7)

        assert calc.total == 177
        assert calc.count == 3
        assert calc.history == (e1, e2, e3)
        assert e1.sequence == 1 and e1.value == 50 and e1.running_total == 50
        assert e2.sequence == 2 and e2.value == 120 and e2.running_total == 170
        assert e3.sequence == 3 and e3.value == 7 and e3.running_total == 177
        assert calc.last_entry == e3

    def test_add_zero(self):
        """Zero is a valid accepted integer that records a history entry."""
        calc = Calculator()
        e1 = calc.add(100)
        e2 = calc.add(0)

        assert calc.total == 100
        assert calc.count == 2
        assert e2.sequence == 2
        assert e2.value == 0
        assert e2.running_total == 100
        assert calc.last_entry == e2

    def test_boundary_additions_0_and_2000(self):
        """Boundary values 0 and 2000 are valid."""
        calc = Calculator()
        calc.add(0)
        calc.add(2000)

        assert calc.total == 2000
        assert calc.count == 2

    def test_undo_single_addition(self):
        """Undo removes the most recent addition and reverts total."""
        calc = Calculator()
        calc.add(50)
        calc.add(120)
        assert calc.total == 170

        removed = calc.undo()
        assert removed is not None
        assert removed.value == 120
        assert calc.total == 50
        assert calc.count == 1
        assert calc.last_entry is not None
        assert calc.last_entry.value == 50

    def test_multiple_undos_lifo_order(self):
        """Successive undos restore previous state in reverse chronological order."""
        calc = Calculator()
        calc.add(10)
        calc.add(20)
        calc.add(30)
        assert calc.total == 60

        u1 = calc.undo()
        assert u1 is not None and u1.value == 30
        assert calc.total == 30

        u2 = calc.undo()
        assert u2 is not None and u2.value == 20
        assert calc.total == 10

        u3 = calc.undo()
        assert u3 is not None and u3.value == 10
        assert calc.total == 0
        assert calc.is_empty is True

    def test_undo_on_empty_history_is_safe(self):
        """Undo on an empty history is a safe no-op returning None."""
        calc = Calculator()
        assert calc.undo() is None
        assert calc.total == 0
        assert calc.is_empty is True

    def test_reset_and_clear(self):
        """Reset / clear removes all entries and sets total to 0."""
        calc = Calculator()
        calc.add(100)
        calc.add(200)
        assert calc.total == 300

        calc.reset()
        assert calc.total == 0
        assert calc.count == 0
        assert calc.is_empty is True
        assert calc.last_entry is None

        # Test clear alias
        calc.add(45)
        calc.clear()
        assert calc.total == 0
        assert calc.is_empty is True

    @pytest.mark.parametrize("invalid_val", [2001, 2002, 5000, 100000])
    def test_reject_out_of_range_positive(self, invalid_val):
        """Values > 2000 raise InvalidValueError."""
        calc = Calculator()
        with pytest.raises(InvalidValueError):
            calc.add(invalid_val)
        assert calc.total == 0

    @pytest.mark.parametrize("negative_val", [-1, -5, -2000])
    def test_reject_negative_values(self, negative_val):
        """Negative values raise InvalidValueError."""
        calc = Calculator()
        with pytest.raises(InvalidValueError):
            calc.add(negative_val)
        assert calc.total == 0

    @pytest.mark.parametrize("non_int_val", [
        50.5, 0.0, 100.0, "50", "one hundred", True, False, None, [10], {"val": 10}
    ])
    def test_reject_non_integer_types(self, non_int_val):
        """Non-integers (floats, strings, booleans, None) raise InvalidValueError."""
        calc = Calculator()
        with pytest.raises(InvalidValueError):
            calc.add(non_int_val)  # type: ignore
        assert calc.total == 0

    def test_state_integrity_after_failed_addition(self):
        """Failed addition does not corrupt or alter previous calculator state."""
        calc = Calculator()
        calc.add(100)
        calc.add(200)
        assert calc.total == 300
        assert calc.count == 2

        with pytest.raises(InvalidValueError):
            calc.add(2500)

        with pytest.raises(InvalidValueError):
            calc.add(-50)

        with pytest.raises(InvalidValueError):
            calc.add("invalid")  # type: ignore

        # State must remain untouched
        assert calc.total == 300
        assert calc.count == 2
        assert [e.value for e in calc.history] == [100, 200]

    def test_total_derived_consistency_property(self):
        """Total is always strictly equal to the sum of active history entries."""
        calc = Calculator()
        values = [15, 30, 0, 45, 100, 500, 1200, 2000]

        for v in values:
            calc.add(v)
            assert calc.total == sum(e.value for e in calc.history)

        while not calc.is_empty:
            calc.undo()
            assert calc.total == sum(e.value for e in calc.history)

    def test_history_entry_immutability(self):
        """HistoryEntry attributes cannot be mutated."""
        calc = Calculator()
        entry = calc.add(75)

        with pytest.raises(FrozenInstanceError):
            entry.value = 99  # type: ignore

        with pytest.raises(FrozenInstanceError):
            entry.running_total = 99  # type: ignore

    def test_history_view_is_immutable_tuple(self):
        """calc.history is a tuple and cannot be modified in-place."""
        calc = Calculator()
        calc.add(10)
        history = calc.history

        assert isinstance(history, tuple)
        with pytest.raises(AttributeError):
            history.append(HistoryEntry(2, 20, 30, 0.0, ""))  # type: ignore

    def test_module_dependency_isolation(self):
        """Calculator module does not import audio, ASR, VAD, GUI, or speech parsing modules."""
        import voice_calculator.calculator as calc_mod

        # Inspect imported modules in calc_mod
        forbidden = ["sounddevice", "vosk", "faster_whisper", "tkinter", "numparse", "vad", "segmenter", "pipeline"]
        for mod_name in sys.modules:
            if any(f in mod_name for f in forbidden):
                # Verify that calc_mod does NOT have these symbols in its namespace
                for f in forbidden:
                    assert not hasattr(calc_mod, f), f"calc_mod contains forbidden dependency {f}"
