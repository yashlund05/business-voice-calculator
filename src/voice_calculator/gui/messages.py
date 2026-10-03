"""User-facing strings, status messages, and formatting constants for Voice Calculator GUI.

Single source of truth for GUI text, status indicators, and plain-language error messages
per docs/design.md §4, §7.
"""

from enum import Enum
from typing import Optional

from voice_calculator.decision import DecisionReason, DecisionResult, DecisionType


class UIState(Enum):
    """High-level GUI state."""

    STOPPED = "STOPPED"                      # Idle, not listening
    LISTENING = "LISTENING"                  # Listening for speech
    PROCESSING = "PROCESSING"                # Processing utterance through ASR/parser
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"  # Candidate number pending user confirmation
    REPEAT_REQUIRED = "REPEAT_REQUIRED"      # Recognition uncertain or audio issue
    ERROR = "ERROR"                          # Hardware or system error


# Status bar colors (high-contrast, distinct)
STATE_COLORS = {
    UIState.STOPPED: "#555555",               # Dark Gray
    UIState.LISTENING: "#1b5e20",             # Dark Green
    UIState.PROCESSING: "#0d47a1",            # Dark Blue
    UIState.AWAITING_CONFIRMATION: "#e65100", # Dark Amber / Orange
    UIState.REPEAT_REQUIRED: "#b71c1c",       # Dark Red / Amber
    UIState.ERROR: "#b71c1c",                 # Dark Red
}

# Status bar text
STATE_TEXTS = {
    UIState.STOPPED: "Not listening — press Start",
    UIState.LISTENING: "Listening — say a number",
    UIState.PROCESSING: "Working it out…",
    UIState.AWAITING_CONFIRMATION: "Please check the number (Enter to Add, Esc to Discard)",
    UIState.REPEAT_REQUIRED: "Didn't catch that — please say the number again.",
    UIState.ERROR: "An error occurred.",
}


# Plain-language messages for controller ERROR events, keyed by error type (prd.md §9)
ERROR_EVENT_MESSAGES = {
    "MicNotFound": "No microphone found. Plug in or enable a microphone, then press Start.",
    "MicBusy": "Microphone is in use or blocked. Check Windows microphone privacy settings, then press Start.",
    "MicLost": "Microphone was disconnected. Listening stopped — check the microphone and press Start.",
    "StreamError": "Microphone stream error. Please press Start to try again.",
}


def get_error_event_message(error_type: Optional[str], fallback: Optional[str]) -> str:
    """Returns the plain-language message for a controller ERROR event.

    Typed audio/model errors map to their prd.md §9 wording; other errors show
    the controller-provided description (or a generic message).
    """
    if error_type and error_type in ERROR_EVENT_MESSAGES:
        return ERROR_EVENT_MESSAGES[error_type]
    return fallback or "An unexpected error occurred."


def format_number(val: Optional[int]) -> str:
    """Formats an integer with thousands separator (e.g. 12450 -> '12,450')."""
    if val is None:
        return "0"
    return f"{val:,}"


def get_decision_feedback_message(decision_res: DecisionResult) -> str:
    """Returns a friendly plain-language status message for a DecisionResult."""
    if decision_res.decision == DecisionType.ACCEPT:
        if decision_res.requires_confirmation:
            return f"Did you say: {format_number(decision_res.value)}?"
        return f"Added: {format_number(decision_res.value)}"

    # Specific diagnostic mapping per design.md §7
    reason = decision_res.reason
    if reason == DecisionReason.NO_SPEECH:
        return "No speech detected — please speak a number."
    elif reason == DecisionReason.PARSER_REJECTED_OUT_OF_RANGE:
        return "That number is too large. I can add numbers up to 2,000."
    elif reason == DecisionReason.UTTERANCE_TOO_LONG:
        return "Please say one number at a time."
    elif reason == DecisionReason.UTTERANCE_DAMAGED:
        return "Audio was interrupted — please say it again."
    elif reason in (DecisionReason.LOW_CONFIDENCE, DecisionReason.UNAVAILABLE_CONFIDENCE):
        return "Didn't catch that clearly — please repeat."
    elif reason == DecisionReason.ASR_ERROR:
        return "Couldn't process that — please say it again."
    elif reason == DecisionReason.SOURCE_ERROR:
        return "Microphone issue — please check microphone and press Start."
    elif reason == DecisionReason.PARSER_REJECTED_NOT_A_NUMBER:
        return "Didn't hear a number — please say a number."
    elif reason in (DecisionReason.PARSER_REJECTED_MALFORMED, DecisionReason.PARSER_REJECTED_AMBIGUOUS):
        return "Didn't catch that clearly — please repeat."

    return "Didn't catch that — please say the number again."
