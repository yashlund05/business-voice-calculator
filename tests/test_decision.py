"""Unit and safety invariant tests for Candidate Safety / Decision Layer (Phase 3.4).

Verifies:
- Safe candidate evaluation (ACCEPT with confirmation required by default).
- Non-accepted outcomes (REPEAT, REJECT) never carry an integer value.
- Hardware/source, ASR, and segmenter errors map to REPEAT with clear diagnostic reasons.
- Parser rejections (malformed, ambiguous, command words, out of range) map to REJECT.
- Confidence policy boundaries and uncalibrated fallback behavior.
- Zero-value confirmation enforcement.
- Result immutability and fail-safe handling of unexpected/corrupt inputs.
- Absolute invariant: zero arithmetic or running total logic in the decision layer.
"""

from dataclasses import FrozenInstanceError
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus
from voice_calculator.decision import (
    DecisionConfig,
    DecisionReason,
    DecisionResult,
    DecisionType,
    SafetyDecisionEngine,
    evaluate_candidate,
)
from voice_calculator.numparse import ParseResult, ParseStatus, RejectReason, parse
from voice_calculator.pipeline import PipelineResult, PipelineStatus


def make_pipeline_result(
    status: PipelineStatus,
    text: str = "",
    confidence: float | None = None,
    error_message: str | None = None,
) -> PipelineResult:
    """Helper to construct synthetic PipelineResult objects for decision testing."""
    asr_res = ASRResult(
        text=text,
        confidence=confidence,
        status=ASRStatus.SUCCESS if status != PipelineStatus.ASR_ERROR else ASRStatus.ERROR,
        error_message=error_message if status == PipelineStatus.ASR_ERROR else None,
    )

    parse_res = None
    if status in (PipelineStatus.PARSED, PipelineStatus.PARSER_REJECTED):
        parse_res = parse(text)

    return PipelineResult(
        status=status,
        asr_result=asr_res,
        parse_result=parse_res,
        error_message=error_message,
    )


class TestSafetyDecisionEngine:
    """Test suite for SafetyDecisionEngine."""

    def test_valid_candidate_accept_default_confirm_all(self):
        """Under default policy (confirm-all), valid parsed numbers are ACCEPT with requires_confirmation=True."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="forty two",
            confidence=None,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.is_accepted is True
        assert result.value == 42
        assert result.reason == DecisionReason.ACCEPTED_CANDIDATE
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert result.confidence is None
        assert result.recognized_text == "forty two"

    def test_valid_candidate_with_auto_accept_enabled(self):
        """When auto_accept_enabled is True and confidence is unconstrained, candidate does not require confirmation."""
        config = DecisionConfig(auto_accept_enabled=True, zero_requires_confirmation=True)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="one hundred fifty",
            confidence=0.95,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 150
        assert result.requires_confirmation is False
        assert result.can_auto_add is True
        assert result.confidence == 0.95

    def test_zero_requires_confirmation_even_when_auto_accept_enabled(self):
        """Zero must require confirmation even when auto_accept_enabled is True (AC-3 / Architecture §9)."""
        config = DecisionConfig(auto_accept_enabled=True, zero_requires_confirmation=True)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="zero",
            confidence=0.99,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 0
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert "Zero requires confirmation" in result.explanation

    def test_confidence_boundary_below_threshold_triggers_repeat(self):
        """When confidence is below min_confidence, candidate is rejected for REPEAT."""
        config = DecisionConfig(min_confidence=0.85)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="fifty",
            confidence=0.62,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.is_repeat is True
        assert result.value is None
        assert result.reason == DecisionReason.LOW_CONFIDENCE
        assert "below safety threshold" in result.explanation

    def test_confidence_boundary_meeting_threshold_is_accepted(self):
        """When confidence meets or exceeds min_confidence, candidate is ACCEPT."""
        config = DecisionConfig(min_confidence=0.85, auto_accept_enabled=False)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="fifty",
            confidence=0.85,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 50
        assert result.reason == DecisionReason.ACCEPTED_CANDIDATE
        assert result.requires_confirmation is True  # auto_accept_enabled is False

    def test_unavailable_confidence_strict_policy_triggers_repeat(self):
        """When require_confidence is True but ASR confidence is None, triggers REPEAT."""
        config = DecisionConfig(require_confidence=True)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="twenty five",
            confidence=None,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.UNAVAILABLE_CONFIDENCE

    def test_parser_rejection_malformed_number_is_rejected(self):
        """Malformed grammar phrases (e.g. 'hundred fifty') are REJECT."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="hundred fifty",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.is_rejected is True
        assert result.value is None
        assert result.reason == DecisionReason.PARSER_REJECTED_MALFORMED

    def test_parser_rejection_ambiguous_phrase_is_rejected(self):
        """Ambiguous phrases (e.g. 'one twenty') are REJECT."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="one twenty",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.value is None
        assert result.reason == DecisionReason.PARSER_REJECTED_AMBIGUOUS

    def test_parser_rejection_command_words_is_rejected(self):
        """Command words and non-numbers (e.g. 'undo', 'stop', 'hello') are REJECT."""
        engine = SafetyDecisionEngine()

        for word in ["undo", "stop", "clear", "hello", "reset", "start"]:
            pipe_res = make_pipeline_result(
                status=PipelineStatus.PARSER_REJECTED,
                text=word,
            )
            result = engine.evaluate(pipe_res)

            assert result.decision == DecisionType.REJECT
            assert result.value is None
            assert result.reason == DecisionReason.PARSER_REJECTED_NOT_A_NUMBER

    def test_parser_rejection_out_of_range_is_rejected(self):
        """Numbers > 2000 (e.g. 'two thousand five') are REJECT with PARSER_REJECTED_OUT_OF_RANGE."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="two thousand five",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.value is None
        assert result.reason == DecisionReason.PARSER_REJECTED_OUT_OF_RANGE

    def test_parser_rejection_multiple_numbers_is_rejected(self):
        """Multiple numbers in one utterance (e.g. 'one two three') are REJECT."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="one two three",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.value is None
        assert result.reason == DecisionReason.PARSER_REJECTED_MULTIPLE_NUMBERS

    def test_parser_rejection_unsupported_math_is_rejected(self):
        """Unsupported representations (e.g. 'minus five', 'three point five') are REJECT."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="minus five",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.value is None
        assert result.reason == DecisionReason.PARSER_REJECTED_UNSUPPORTED

    def test_no_speech_triggers_repeat(self):
        """Silence / non-speech is REPEAT with NO_SPEECH reason."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.NO_SPEECH,
            text="",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.NO_SPEECH

    def test_asr_error_triggers_repeat(self):
        """ASR engine error is REPEAT with ASR_ERROR reason."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.ASR_ERROR,
            error_message="Decoder buffer underflow",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.ASR_ERROR
        assert "Decoder buffer underflow" in result.explanation

    def test_source_error_triggers_repeat(self):
        """Hardware/source error is REPEAT with SOURCE_ERROR reason."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.SOURCE_ERROR,
            error_message="Microphone unplugged",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.SOURCE_ERROR
        assert "Microphone unplugged" in result.explanation

    def test_damaged_utterance_triggers_repeat(self):
        """Audio frame drop/overflow is REPEAT with UTTERANCE_DAMAGED reason."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.DAMAGED,
            error_message="Queue dropped 2 frames",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.UTTERANCE_DAMAGED

    def test_too_long_utterance_triggers_repeat(self):
        """Utterance exceeding max duration cap is REPEAT with UTTERANCE_TOO_LONG reason."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.TOO_LONG,
            error_message="Exceeded 6000ms duration cap",
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REPEAT
        assert result.value is None
        assert result.reason == DecisionReason.UTTERANCE_TOO_LONG

    def test_convenience_function_evaluate_candidate(self):
        """Convenience function evaluate_candidate() produces matching results."""
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="seven hundred",
            confidence=0.9,
        )

        result = evaluate_candidate(pipe_res)
        assert result.decision == DecisionType.ACCEPT
        assert result.value == 700

    def test_result_immutability(self):
        """DecisionResult is frozen and cannot be mutated."""
        result = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=100,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
        )

        with pytest.raises(FrozenInstanceError):
            result.value = 200  # type: ignore

    def test_unexpected_input_fails_safely(self):
        """Passing None or invalid object fails safely with REJECT and UNKNOWN_STATUS."""
        engine = SafetyDecisionEngine()

        res1 = engine.evaluate(None)
        assert res1.decision == DecisionType.REJECT
        assert res1.value is None
        assert res1.reason == DecisionReason.UNKNOWN_STATUS

        res2 = engine.evaluate("not a pipeline result")  # type: ignore
        assert res2.decision == DecisionType.REJECT
        assert res2.value is None
        assert res2.reason == DecisionReason.UNKNOWN_STATUS

    def test_no_arithmetic_or_running_total_invariants(self):
        """Verify that DecisionResult and SafetyDecisionEngine do not perform arithmetic or track state."""
        engine = SafetyDecisionEngine()

        res1 = engine.evaluate(make_pipeline_result(PipelineStatus.PARSED, text="ten"))
        res2 = engine.evaluate(make_pipeline_result(PipelineStatus.PARSED, text="twenty"))

        assert res1.value == 10
        assert res2.value == 20
        # Check that no total attribute or cumulative state exists
        assert not hasattr(engine, "total")
        assert not hasattr(engine, "running_total")
        assert not hasattr(engine, "history")
        assert not hasattr(res1, "total")
        assert not hasattr(res2, "total")
