"""Candidate safety and decision layer for Voice Calculator.

Receives structured PipelineResult instances from the audio pipeline and
deterministically evaluates whether candidate utterances should be:
1. ACCEPT — safe numerical candidate for downstream calculation/confirmation.
2. REPEAT — user should repeat (silence, ASR failure, low confidence, audio distortion).
3. REJECT — definitely not a supported number (grammar error, command word, out of range).

Safety Invariants:
- A successful parser candidate is NEVER automatically equivalent to permission to add.
- "Repeat is better than a wrong total."
- Non-accepted results (REPEAT, REJECT) NEVER carry an integer value.
- Decision results are frozen and immutable.
- Zero arithmetic or running-total logic is performed in this layer.
- Fails safely on any unexpected or unhandled input.
"""

from dataclasses import dataclass
from enum import Enum
import logging
from typing import Optional

from voice_calculator.config import (
    AUTO_ACCEPT_ENABLED,
    MAX_NUMBER,
    MIN_NUMBER,
    ZERO_REQUIRES_CONFIRMATION,
)
from voice_calculator.numparse import RejectReason
from voice_calculator.pipeline import PipelineResult, PipelineStatus

logger = logging.getLogger("voice_calculator.decision")


class DecisionType(Enum):
    """Tri-state safety decision classification."""

    ACCEPT = "ACCEPT"  # Valid candidate; eligible for confirmation or auto-addition
    REPEAT = "REPEAT"  # Audio/ASR/confidence uncertainty; user should repeat
    REJECT = "REJECT"  # Definitely not a supported number or invalid linguistic structure


class DecisionReason(Enum):
    """Detailed diagnostic reason explaining the decision."""

    # Success / Acceptance
    ACCEPTED_CANDIDATE = "ACCEPTED_CANDIDATE"

    # Audio & Hardware issues (REPEAT)
    NO_SPEECH = "NO_SPEECH"
    ASR_ERROR = "ASR_ERROR"
    SOURCE_ERROR = "SOURCE_ERROR"
    UTTERANCE_TOO_LONG = "UTTERANCE_TOO_LONG"
    UTTERANCE_DAMAGED = "UTTERANCE_DAMAGED"

    # Confidence policy issues (REPEAT)
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNAVAILABLE_CONFIDENCE = "UNAVAILABLE_CONFIDENCE"

    # Parser linguistic rejections (REJECT)
    PARSER_REJECTED_NOT_A_NUMBER = "PARSER_REJECTED_NOT_A_NUMBER"
    PARSER_REJECTED_OUT_OF_RANGE = "PARSER_REJECTED_OUT_OF_RANGE"
    PARSER_REJECTED_MALFORMED = "PARSER_REJECTED_MALFORMED"
    PARSER_REJECTED_AMBIGUOUS = "PARSER_REJECTED_AMBIGUOUS"
    PARSER_REJECTED_UNSUPPORTED = "PARSER_REJECTED_UNSUPPORTED"
    PARSER_REJECTED_MULTIPLE_NUMBERS = "PARSER_REJECTED_MULTIPLE_NUMBERS"
    PARSER_REJECTED_EMPTY = "PARSER_REJECTED_EMPTY"
    PARSER_REJECTED_UNKNOWN = "PARSER_REJECTED_UNKNOWN"

    # Fallback / Error
    UNKNOWN_STATUS = "UNKNOWN_STATUS"


@dataclass(frozen=True)
class DecisionConfig:
    """Configurable policy thresholds for safety evaluation."""

    auto_accept_enabled: bool = AUTO_ACCEPT_ENABLED
    zero_requires_confirmation: bool = ZERO_REQUIRES_CONFIRMATION
    min_confidence: Optional[float] = None  # None = uncalibrated threshold (not enforced)
    require_confidence: bool = False       # If True, missing confidence triggers REPEAT
    min_number: int = MIN_NUMBER
    max_number: int = MAX_NUMBER


@dataclass(frozen=True)
class DecisionResult:
    """Immutable structured outcome from the candidate safety/decision layer.

    Attributes:
        decision: High-level classification (ACCEPT, REPEAT, REJECT).
        value: The parsed candidate integer if decision is ACCEPT, otherwise None.
        reason: Diagnostic reason enum.
        requires_confirmation: True if manual user confirmation is required before adding.
        explanation: Human-readable explanation for logs / UI messages.
        confidence: ASR acoustic/language confidence if available.
        recognized_text: Spoken text transcribed by ASR.
        pipeline_status: Raw pipeline status that was evaluated.
    """

    decision: DecisionType
    value: Optional[int] = None
    reason: DecisionReason = DecisionReason.UNKNOWN_STATUS
    requires_confirmation: bool = True
    explanation: str = ""
    confidence: Optional[float] = None
    recognized_text: str = ""
    pipeline_status: Optional[PipelineStatus] = None

    @property
    def is_accepted(self) -> bool:
        """True if the candidate was accepted as a valid number."""
        return self.decision == DecisionType.ACCEPT

    @property
    def is_repeat(self) -> bool:
        """True if the user should repeat their utterance."""
        return self.decision == DecisionType.REPEAT

    @property
    def is_rejected(self) -> bool:
        """True if the input is definitely rejected."""
        return self.decision == DecisionType.REJECT

    @property
    def can_auto_add(self) -> bool:
        """True if and only if the candidate is accepted AND auto-accept policy permits addition without confirmation."""
        return self.decision == DecisionType.ACCEPT and not self.requires_confirmation


class SafetyDecisionEngine:
    """Evaluates PipelineResults and produces deterministic DecisionResults."""

    def __init__(self, config: Optional[DecisionConfig] = None) -> None:
        self.config = config or DecisionConfig()

    def evaluate(self, pipeline_result: Optional[PipelineResult]) -> DecisionResult:
        """Evaluates a single PipelineResult against deterministic safety rules.

        Args:
            pipeline_result: Output from AudioPipeline.

        Returns:
            Immutable DecisionResult.
        """
        try:
            return self._evaluate_internal(pipeline_result)
        except Exception as e:
            logger.error("Unexpected exception during safety decision evaluation: %s", type(e).__name__)
            return DecisionResult(
                decision=DecisionType.REJECT,
                value=None,
                reason=DecisionReason.UNKNOWN_STATUS,
                requires_confirmation=False,
                explanation=f"Internal decision evaluation exception: {e}",
                pipeline_status=getattr(pipeline_result, "status", None),
            )

    def _evaluate_internal(self, pipeline_result: Optional[PipelineResult]) -> DecisionResult:
        if pipeline_result is None or not isinstance(pipeline_result, PipelineResult):
            logger.warning("SafetyDecisionEngine received invalid or None pipeline_result.")
            return DecisionResult(
                decision=DecisionType.REJECT,
                value=None,
                reason=DecisionReason.UNKNOWN_STATUS,
                requires_confirmation=False,
                explanation="Invalid or null pipeline result received.",
            )

        status = pipeline_result.status

        # 1. Source / Hardware errors -> REPEAT
        if status == PipelineStatus.SOURCE_ERROR:
            return DecisionResult(
                decision=DecisionType.REPEAT,
                value=None,
                reason=DecisionReason.SOURCE_ERROR,
                requires_confirmation=False,
                explanation=pipeline_result.error_message or "Microphone capture error; please repeat.",
                recognized_text=pipeline_result.recognized_text,
                pipeline_status=status,
            )

        # 2. ASR Engine errors -> REPEAT
        if status == PipelineStatus.ASR_ERROR:
            return DecisionResult(
                decision=DecisionType.REPEAT,
                value=None,
                reason=DecisionReason.ASR_ERROR,
                requires_confirmation=False,
                explanation=pipeline_result.error_message or "Speech recognition failed; please repeat.",
                recognized_text=pipeline_result.recognized_text,
                pipeline_status=status,
            )

        # 3. No speech / silence -> REPEAT
        if status == PipelineStatus.NO_SPEECH:
            return DecisionResult(
                decision=DecisionType.REPEAT,
                value=None,
                reason=DecisionReason.NO_SPEECH,
                requires_confirmation=False,
                explanation="No clear speech detected; please repeat.",
                recognized_text="",
                pipeline_status=status,
            )

        # 4. Utterance duration exceeded cap -> REPEAT
        if status == PipelineStatus.TOO_LONG:
            return DecisionResult(
                decision=DecisionType.REPEAT,
                value=None,
                reason=DecisionReason.UTTERANCE_TOO_LONG,
                requires_confirmation=False,
                explanation=pipeline_result.error_message or "Utterance was too long; please speak shorter numbers.",
                recognized_text="",
                pipeline_status=status,
            )

        # 5. Audio damaged / queue overflow -> REPEAT
        if status == PipelineStatus.DAMAGED:
            return DecisionResult(
                decision=DecisionType.REPEAT,
                value=None,
                reason=DecisionReason.UTTERANCE_DAMAGED,
                requires_confirmation=False,
                explanation=pipeline_result.error_message or "Audio queue overflow occurred; please repeat.",
                recognized_text="",
                pipeline_status=status,
            )

        # 6. Parser rejection -> REJECT with specific linguistic reason
        if status == PipelineStatus.PARSER_REJECTED:
            reason_map = {
                RejectReason.NOT_A_NUMBER: (
                    DecisionReason.PARSER_REJECTED_NOT_A_NUMBER,
                    "Not a recognized number phrase or command word ignored.",
                ),
                RejectReason.OUT_OF_RANGE: (
                    DecisionReason.PARSER_REJECTED_OUT_OF_RANGE,
                    "Spoken number is outside the supported range (0–2000).",
                ),
                RejectReason.MALFORMED: (
                    DecisionReason.PARSER_REJECTED_MALFORMED,
                    "Malformed number grammar structure.",
                ),
                RejectReason.AMBIGUOUS: (
                    DecisionReason.PARSER_REJECTED_AMBIGUOUS,
                    "Ambiguous colloquial number phrasing.",
                ),
                RejectReason.UNSUPPORTED: (
                    DecisionReason.PARSER_REJECTED_UNSUPPORTED,
                    "Unsupported mathematical representation.",
                ),
                RejectReason.MULTIPLE_NUMBERS: (
                    DecisionReason.PARSER_REJECTED_MULTIPLE_NUMBERS,
                    "Multiple numbers detected in a single utterance.",
                ),
                RejectReason.EMPTY: (
                    DecisionReason.PARSER_REJECTED_EMPTY,
                    "Empty speech transcript.",
                ),
            }

            reason_enum, explanation = reason_map.get(
                pipeline_result.reject_reason,
                (DecisionReason.PARSER_REJECTED_UNKNOWN, "Parser rejected transcript."),
            )

            return DecisionResult(
                decision=DecisionType.REJECT,
                value=None,
                reason=reason_enum,
                requires_confirmation=False,
                explanation=explanation,
                confidence=pipeline_result.confidence,
                recognized_text=pipeline_result.recognized_text,
                pipeline_status=status,
            )

        # 7. Parsed candidate integer -> Evaluate confidence & confirmation policies
        if status == PipelineStatus.PARSED:
            parsed_val = pipeline_result.parsed_value
            if parsed_val is None:
                # Invariant violation fail-safe
                logger.error("PipelineStatus is PARSED but parsed_value is None.")
                return DecisionResult(
                    decision=DecisionType.REJECT,
                    value=None,
                    reason=DecisionReason.UNKNOWN_STATUS,
                    requires_confirmation=False,
                    explanation="Parser indicated success but produced no integer value.",
                    pipeline_status=status,
                )

            # Extra boundary safety check
            if not (self.config.min_number <= parsed_val <= self.config.max_number):
                return DecisionResult(
                    decision=DecisionType.REJECT,
                    value=None,
                    reason=DecisionReason.PARSER_REJECTED_OUT_OF_RANGE,
                    requires_confirmation=False,
                    explanation=f"Value {parsed_val} is outside allowed range {self.config.min_number}–{self.config.max_number}.",
                    recognized_text=pipeline_result.recognized_text,
                    pipeline_status=status,
                )

            conf = pipeline_result.confidence

            # Policy check: Confidence handling
            if conf is None:
                if self.config.require_confidence:
                    return DecisionResult(
                        decision=DecisionType.REPEAT,
                        value=None,
                        reason=DecisionReason.UNAVAILABLE_CONFIDENCE,
                        requires_confirmation=False,
                        explanation="Confidence score unavailable under strict confidence policy; please repeat.",
                        confidence=None,
                        recognized_text=pipeline_result.recognized_text,
                        pipeline_status=status,
                    )
                # Uncalibrated / absent confidence: safe conservative policy (requires confirmation)
                requires_confirm = True
                explanation = f"Candidate integer {parsed_val} parsed successfully (confidence unavailable, confirmation required)."
            else:
                # Calibrated / configured confidence threshold check
                if self.config.min_confidence is not None and conf < self.config.min_confidence:
                    return DecisionResult(
                        decision=DecisionType.REPEAT,
                        value=None,
                        reason=DecisionReason.LOW_CONFIDENCE,
                        requires_confirmation=False,
                        explanation=(
                            f"Confidence {conf:.2f} is below safety threshold "
                            f"{self.config.min_confidence:.2f}; please repeat."
                        ),
                        confidence=conf,
                        recognized_text=pipeline_result.recognized_text,
                        pipeline_status=status,
                    )

                if self.config.auto_accept_enabled:
                    requires_confirm = False
                    explanation = f"Candidate integer {parsed_val} parsed successfully with confidence {conf:.2f}."
                else:
                    requires_confirm = True
                    explanation = f"Candidate integer {parsed_val} parsed successfully (confirm-all policy active)."

            # Policy check: Zero confirmation rule
            if parsed_val == 0 and self.config.zero_requires_confirmation:
                requires_confirm = True
                if not explanation.endswith("(Zero requires confirmation)."):
                    explanation += " (Zero requires confirmation)."

            return DecisionResult(
                decision=DecisionType.ACCEPT,
                value=parsed_val,
                reason=DecisionReason.ACCEPTED_CANDIDATE,
                requires_confirmation=requires_confirm,
                explanation=explanation,
                confidence=conf,
                recognized_text=pipeline_result.recognized_text,
                pipeline_status=status,
            )

        # Fallback for any unknown pipeline status
        logger.warning("Encountered unhandled pipeline status: %s", status)
        return DecisionResult(
            decision=DecisionType.REJECT,
            value=None,
            reason=DecisionReason.UNKNOWN_STATUS,
            requires_confirmation=False,
            explanation=f"Unhandled pipeline status: {status}",
            pipeline_status=status,
        )


def evaluate_candidate(
    pipeline_result: Optional[PipelineResult],
    config: Optional[DecisionConfig] = None,
) -> DecisionResult:
    """Convenience helper to evaluate a PipelineResult with SafetyDecisionEngine."""
    return SafetyDecisionEngine(config=config).evaluate(pipeline_result)
