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

Phase 5B additions (Confirmation & Recovery Reliability):
- Defense-in-depth: PARSED status with missing parse value and out-of-range values reaching the
  engine directly are fail-safely rejected.
- Value-masking sweep: every abnormal pipeline status and every parser rejection reason yields a
  decision with value=None and no confirmation requirement.
- Zero rule enforced under the default Safe Mode policy.
"""

from dataclasses import FrozenInstanceError
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus
from voice_calculator.decision import (
    DecisionConfig,
    DecisionReason,
    DecisionResult,
    DecisionType,
    OperatingMode,
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

    def test_safe_mode_strictly_requires_confirmation_even_with_high_confidence(self):
        """In Safe Mode, every valid candidate requires confirmation even with high confidence and auto_accept_enabled=True."""
        config = DecisionConfig(mode=OperatingMode.SAFE, auto_accept_enabled=True, zero_requires_confirmation=True)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="one hundred fifty",
            confidence=0.99,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 150
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert result.mode == OperatingMode.SAFE

    def test_fast_mode_with_auto_accept_enabled_and_confidence(self):
        """In Fast Mode with auto_accept_enabled and calibrated confidence, candidate can auto-add."""
        config = DecisionConfig(mode=OperatingMode.FAST, auto_accept_enabled=True, zero_requires_confirmation=True)
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
        assert result.mode == OperatingMode.FAST

    def test_fast_mode_with_missing_confidence_requires_confirmation(self):
        """In Fast Mode, missing/uncalibrated confidence (e.g. Vosk baseline) MUST require confirmation."""
        config = DecisionConfig(mode=OperatingMode.FAST, auto_accept_enabled=True)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="forty two",
            confidence=None,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 42
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert "confidence unavailable" in result.explanation

    def test_fast_mode_with_auto_accept_disabled_requires_confirmation(self):
        """In Fast Mode with auto_accept_enabled=False (gated), candidate requires confirmation."""
        config = DecisionConfig(mode=OperatingMode.FAST, auto_accept_enabled=False)
        engine = SafetyDecisionEngine(config=config)
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="fifty",
            confidence=0.95,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 50
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert "auto-accept gated" in result.explanation

    def test_zero_requires_confirmation_even_when_auto_accept_enabled(self):
        """Zero must require confirmation even when auto_accept_enabled is True in Fast Mode (AC-3 / Architecture §9)."""
        config = DecisionConfig(mode=OperatingMode.FAST, auto_accept_enabled=True, zero_requires_confirmation=True)
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
        """Malformed grammar phrases (e.g. 'ten hundred') are REJECT."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSER_REJECTED,
            text="ten hundred",
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

    def test_engine_dynamic_mode_switching(self):
        """Verify that set_mode dynamically updates operating mode without recreating engine."""
        config = DecisionConfig(mode=OperatingMode.SAFE, auto_accept_enabled=True)
        engine = SafetyDecisionEngine(config=config)
        assert engine.mode == OperatingMode.SAFE

        pipe_res = make_pipeline_result(PipelineStatus.PARSED, text="one hundred", confidence=0.95)

        # In Safe Mode -> requires confirmation
        res_safe = engine.evaluate(pipe_res)
        assert res_safe.requires_confirmation is True
        assert res_safe.mode == OperatingMode.SAFE

        # Switch to Fast Mode -> auto accepts
        engine.set_mode(OperatingMode.FAST)
        assert engine.mode == OperatingMode.FAST

        res_fast = engine.evaluate(pipe_res)
        assert res_fast.requires_confirmation is False
        assert res_fast.mode == OperatingMode.FAST

        # Switch back to Safe Mode -> requires confirmation again
        engine.set_mode(OperatingMode.SAFE)
        assert engine.mode == OperatingMode.SAFE
        res_safe_again = engine.evaluate(pipe_res)
        assert res_safe_again.requires_confirmation is True

    def test_fast_mode_preserves_rejection_of_invalid_and_out_of_range(self):
        """Fast Mode must never accept invalid, out of range, or command words."""
        config = DecisionConfig(mode=OperatingMode.FAST, auto_accept_enabled=True)
        engine = SafetyDecisionEngine(config=config)

        # Malformed
        res_malformed = engine.evaluate(make_pipeline_result(PipelineStatus.PARSER_REJECTED, text="hundred fifty", confidence=0.99))
        assert res_malformed.decision == DecisionType.REJECT
        assert res_malformed.value is None

        # Command word
        res_cmd = engine.evaluate(make_pipeline_result(PipelineStatus.PARSER_REJECTED, text="undo", confidence=0.99))
        assert res_cmd.decision == DecisionType.REJECT
        assert res_cmd.value is None

        # Out of range
        res_range = engine.evaluate(make_pipeline_result(PipelineStatus.PARSER_REJECTED, text="five thousand", confidence=0.99))
        assert res_range.decision == DecisionType.REJECT
        assert res_range.value is None


class TestDecisionReliabilityInvariants:
    """Phase 5B: confirmation & recovery reliability invariants of the decision layer."""

    def test_parsed_status_with_null_parse_result_fails_safely(self):
        """PARSED status with a missing parse result must fail safely to REJECT with no value."""
        engine = SafetyDecisionEngine()
        pipe_res = PipelineResult(
            status=PipelineStatus.PARSED,
            asr_result=ASRResult(text="fifty", status=ASRStatus.SUCCESS),
            parse_result=None,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.REJECT
        assert result.value is None
        assert result.reason == DecisionReason.UNKNOWN_STATUS
        assert result.requires_confirmation is False

    def test_out_of_range_value_boundary_check_defense_in_depth(self):
        """Out-of-range values reaching the engine directly (bypassing parser bounds) are rejected."""
        engine = SafetyDecisionEngine()

        # Above the supported maximum (0-2000)
        pipe_high = PipelineResult(
            status=PipelineStatus.PARSED,
            asr_result=ASRResult(text="five thousand", status=ASRStatus.SUCCESS),
            parse_result=ParseResult(status=ParseStatus.SUCCESS, value=5000),
        )
        res_high = engine.evaluate(pipe_high)
        assert res_high.decision == DecisionType.REJECT
        assert res_high.value is None
        assert res_high.reason == DecisionReason.PARSER_REJECTED_OUT_OF_RANGE

        # Below the supported minimum
        pipe_negative = PipelineResult(
            status=PipelineStatus.PARSED,
            asr_result=ASRResult(text="minus five", status=ASRStatus.SUCCESS),
            parse_result=ParseResult(status=ParseStatus.SUCCESS, value=-3),
        )
        res_negative = engine.evaluate(pipe_negative)
        assert res_negative.decision == DecisionType.REJECT
        assert res_negative.value is None
        assert res_negative.reason == DecisionReason.PARSER_REJECTED_OUT_OF_RANGE

    def test_value_masking_invariant_sweep_all_abnormal_paths(self):
        """Every abnormal pipeline status and parser rejection reason masks the value to None."""
        engine = SafetyDecisionEngine()

        # Hardware / ASR / silence / duration / damage paths -> REPEAT with no value
        repeat_statuses = [
            PipelineStatus.NO_SPEECH,
            PipelineStatus.ASR_ERROR,
            PipelineStatus.SOURCE_ERROR,
            PipelineStatus.TOO_LONG,
            PipelineStatus.DAMAGED,
        ]
        for status in repeat_statuses:
            res = engine.evaluate(make_pipeline_result(status, error_message="simulated failure"))
            assert res.decision == DecisionType.REPEAT, f"Unexpected decision for {status}"
            assert res.value is None, f"Value leaked for {status}"
            assert res.requires_confirmation is False, f"Confirmation required for {status}"

        # Every parser rejection reason -> REJECT with no value
        for reject_reason in RejectReason:
            pipe_res = PipelineResult(
                status=PipelineStatus.PARSER_REJECTED,
                asr_result=ASRResult(text="junk transcript", status=ASRStatus.SUCCESS),
                parse_result=ParseResult(status=ParseStatus.REJECTED, reason=reject_reason),
            )
            res = engine.evaluate(pipe_res)
            assert res.decision == DecisionType.REJECT, f"Unexpected decision for {reject_reason}"
            assert res.value is None, f"Value leaked for {reject_reason}"
            assert res.requires_confirmation is False, f"Confirmation required for {reject_reason}"
            assert res.reason.name.startswith("PARSER_REJECTED"), (
                f"Unexpected reason mapping for {reject_reason}"
            )

    def test_zero_requires_confirmation_in_default_safe_mode(self):
        """Under the default Safe Mode policy, zero is accepted only with manual confirmation."""
        engine = SafetyDecisionEngine()
        pipe_res = make_pipeline_result(
            status=PipelineStatus.PARSED,
            text="zero",
            confidence=None,
        )

        result = engine.evaluate(pipe_res)

        assert result.decision == DecisionType.ACCEPT
        assert result.value == 0
        assert result.requires_confirmation is True
        assert result.can_auto_add is False
        assert "Zero requires confirmation" in result.explanation
