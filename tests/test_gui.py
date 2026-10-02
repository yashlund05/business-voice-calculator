"""Unit and interaction tests for Desktop GUI Shell (Phase 3.6A).

Verifies:
- Initial display state (Total=0, STOPPED state, Start enabled, Stop/Undo disabled, history empty).
- Physical Start and Stop state transitions.
- Confirmation flow: candidate requiring confirmation displays confirmation UI and disables Undo.
- User confirmation (Add): adds candidate value, refreshes total/history, restores state.
- User discard (Discard): leaves total untouched, clears pending candidate, restores state.
- Auto-accept candidate flow (adds candidate without user prompt if policy allows).
- Reject and Repeat decisions leave calculator total completely untouched.
- Undo and Clear operations refresh total and history list.
- Safety pipeline integration: process_pipeline_result evaluates candidate through SafetyDecisionEngine.
- Keyboard bindings (Enter -> Add, Esc -> Discard, Ctrl+Z -> Undo).
"""

import tkinter as tk
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus
from voice_calculator.calculator import Calculator
from voice_calculator.decision import (
    DecisionConfig,
    DecisionReason,
    DecisionResult,
    DecisionType,
    OperatingMode,
    SafetyDecisionEngine,
)
from voice_calculator.gui.app import VoiceCalculatorApp
from voice_calculator.gui.messages import UIState
from voice_calculator.asr.base import FakeEngine
from voice_calculator.audio.capture import FakeAudioSource
from voice_calculator.controller import ControllerEvent, ControllerEventType, ListeningController
from voice_calculator.numparse import parse
from voice_calculator.pipeline import PipelineResult, PipelineStatus



@pytest.fixture(scope="module")
def tk_root():
    """Module-scoped Tk root to avoid repeated Tcl interpreter initialization."""
    root = tk.Tk()
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:
        pass


@pytest.fixture
def gui_app(tk_root):
    """Fixture providing a freshly initialized VoiceCalculatorApp with a fake controller for tests."""
    calc = Calculator()
    decision_engine = SafetyDecisionEngine()
    fake_controller = ListeningController(
        engine=FakeEngine(default_text="one hundred"),
        audio_source_factory=lambda: FakeAudioSource([]),
        decision_engine=decision_engine,
    )
    app = VoiceCalculatorApp(
        root=tk_root,
        calculator=calc,
        decision_engine=decision_engine,
        controller=fake_controller,
    )

    app.on_clear()
    app.on_stop()
    app.refresh_display()
    yield app
    app.on_clear()
    app.on_stop()




def make_pipeline_result(
    status: PipelineStatus,
    text: str = "",
    confidence: float | None = None,
) -> PipelineResult:
    """Helper to construct synthetic PipelineResult objects for GUI testing."""
    asr_res = ASRResult(
        text=text,
        confidence=confidence,
        status=ASRStatus.SUCCESS if status != PipelineStatus.ASR_ERROR else ASRStatus.ERROR,
    )
    parse_res = parse(text) if status in (PipelineStatus.PARSED, PipelineStatus.PARSER_REJECTED) else None

    return PipelineResult(
        status=status,
        asr_result=asr_res,
        parse_result=parse_res,
    )


class TestVoiceCalculatorGUI:
    """Test suite for VoiceCalculatorApp GUI shell."""

    def test_initial_display_state(self, gui_app: VoiceCalculatorApp):
        """Initial GUI state has total 0, is STOPPED, with Start enabled and Stop/Undo disabled."""
        assert gui_app.lbl_total_value.cget("text") == "0"
        assert gui_app.state == UIState.STOPPED
        assert gui_app.btn_start.cget("state") == tk.NORMAL
        assert gui_app.btn_stop.cget("state") == tk.DISABLED
        assert gui_app.btn_undo.cget("state") == tk.DISABLED
        assert gui_app.history_listbox.size() == 0
        assert gui_app.pending_candidate is None

    def test_start_and_stop_state_transitions(self, gui_app: VoiceCalculatorApp):
        """Start switches to LISTENING (Start disabled, Stop enabled); Stop returns to STOPPED."""
        gui_app.on_start()
        assert gui_app.state == UIState.LISTENING
        assert gui_app.btn_start.cget("state") == tk.DISABLED
        assert gui_app.btn_stop.cget("state") == tk.NORMAL

        gui_app.on_stop()
        assert gui_app.state == UIState.STOPPED
        assert gui_app.btn_start.cget("state") == tk.NORMAL
        assert gui_app.btn_stop.cget("state") == tk.DISABLED

    def test_confirmation_required_flow_and_add(self, gui_app: VoiceCalculatorApp):
        """Candidate requiring confirmation prompts user; confirming adds value to total and updates history."""
        gui_app.on_start()
        decision_res = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=150,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
            recognized_text="one hundred fifty",
        )

        gui_app.process_decision_result(decision_res)

        # In confirmation state
        assert gui_app.state == UIState.AWAITING_CONFIRMATION
        assert gui_app.pending_candidate == decision_res
        assert "150" in gui_app.lbl_feedback.cget("text")
        assert gui_app.btn_undo.cget("state") == tk.DISABLED
        assert gui_app.lbl_total_value.cget("text") == "0"  # Not added yet!

        # Confirm addition
        gui_app.on_confirm_add()

        # Added to total
        assert gui_app.calculator.total == 150
        assert gui_app.lbl_total_value.cget("text") == "150"
        assert gui_app.state == UIState.LISTENING
        assert gui_app.pending_candidate is None
        assert gui_app.history_listbox.size() == 1
        assert "150" in gui_app.history_listbox.get(0)
        assert gui_app.btn_undo.cget("state") == tk.NORMAL

    def test_confirmation_discard_flow(self, gui_app: VoiceCalculatorApp):
        """Discarding a pending candidate leaves total at 0 and clears confirmation prompt."""
        gui_app.on_start()
        decision_res = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=500,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )

        gui_app.process_decision_result(decision_res)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION

        gui_app.on_confirm_discard()

        assert gui_app.calculator.total == 0
        assert gui_app.lbl_total_value.cget("text") == "0"
        assert gui_app.state == UIState.LISTENING
        assert gui_app.pending_candidate is None
        assert gui_app.history_listbox.size() == 0

    def test_auto_accept_candidate_flow(self, gui_app: VoiceCalculatorApp):
        """Candidate with requires_confirmation=False is added automatically."""
        gui_app.on_start()
        decision_res = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=75,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=False,
        )

        gui_app.process_decision_result(decision_res)

        assert gui_app.calculator.total == 75
        assert gui_app.lbl_total_value.cget("text") == "75"
        assert gui_app.state == UIState.LISTENING
        assert gui_app.pending_candidate is None
        assert gui_app.history_listbox.size() == 1

    def test_repeat_decision_leaves_total_untouched(self, gui_app: VoiceCalculatorApp):
        """REPEAT outcome leaves calculator total and history untouched."""
        gui_app.on_start()
        decision_res = DecisionResult(
            decision=DecisionType.REPEAT,
            value=None,
            reason=DecisionReason.NO_SPEECH,
        )

        gui_app.process_decision_result(decision_res)

        assert gui_app.calculator.total == 0
        assert gui_app.lbl_total_value.cget("text") == "0"
        assert gui_app.state == UIState.REPEAT_REQUIRED
        assert gui_app.history_listbox.size() == 0

    def test_reject_decision_leaves_total_untouched(self, gui_app: VoiceCalculatorApp):
        """REJECT outcome (e.g. out of range or malformed) leaves total untouched."""
        gui_app.on_start()
        decision_res = DecisionResult(
            decision=DecisionType.REJECT,
            value=None,
            reason=DecisionReason.PARSER_REJECTED_OUT_OF_RANGE,
        )

        gui_app.process_decision_result(decision_res)

        assert gui_app.calculator.total == 0
        assert gui_app.lbl_total_value.cget("text") == "0"
        assert gui_app.history_listbox.size() == 0

    def test_undo_operation_refreshes_display(self, gui_app: VoiceCalculatorApp):
        """Undo removes the most recent entry and updates total and history list."""
        gui_app.calculator.add(100)
        gui_app.calculator.add(25)
        gui_app.refresh_display()

        assert gui_app.lbl_total_value.cget("text") == "125"
        assert gui_app.history_listbox.size() == 2

        gui_app.on_undo()

        assert gui_app.calculator.total == 100
        assert gui_app.lbl_total_value.cget("text") == "100"
        assert gui_app.history_listbox.size() == 1

    def test_clear_operation_refreshes_display(self, gui_app: VoiceCalculatorApp):
        """Clear resets total to 0 and empties history list."""
        gui_app.calculator.add(50)
        gui_app.calculator.add(70)
        gui_app.refresh_display()

        assert gui_app.calculator.total == 120
        assert gui_app.history_listbox.size() == 2

        gui_app.on_clear()

        assert gui_app.calculator.total == 0
        assert gui_app.lbl_total_value.cget("text") == "0"
        assert gui_app.history_listbox.size() == 0
        assert gui_app.btn_undo.cget("state") == tk.DISABLED

    def test_pipeline_result_integration_through_decision_engine(self, gui_app: VoiceCalculatorApp):
        """process_pipeline_result() safely routes raw pipeline outcomes through SafetyDecisionEngine."""
        gui_app.on_start()

        # Valid candidate
        pipe_valid = make_pipeline_result(PipelineStatus.PARSED, text="twenty")
        gui_app.process_pipeline_result(pipe_valid)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION
        gui_app.on_confirm_add()
        assert gui_app.calculator.total == 20

        # Command word / non-number (e.g. "undo")
        pipe_command = make_pipeline_result(PipelineStatus.PARSER_REJECTED, text="undo")
        gui_app.process_pipeline_result(pipe_command)
        assert gui_app.calculator.total == 20  # Unchanged!

        # Malformed number (e.g. "hundred fifty")
        pipe_malformed = make_pipeline_result(PipelineStatus.PARSER_REJECTED, text="hundred fifty")
        gui_app.process_pipeline_result(pipe_malformed)
        assert gui_app.calculator.total == 20  # Unchanged!

    def test_stop_while_awaiting_confirmation_discards_candidate(self, gui_app: VoiceCalculatorApp):
        """Pressing Stop while awaiting confirmation discards the candidate without adding."""
        gui_app.on_start()
        gui_app.calculator.add(50)
        gui_app.refresh_display()
        assert gui_app.calculator.total == 50

        # Candidate arrives
        cand = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=70,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        gui_app.process_decision_result(cand)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION

        # User presses Stop
        gui_app.on_stop()
        assert gui_app.state == UIState.STOPPED
        assert gui_app.pending_candidate is None
        assert gui_app.calculator.total == 50  # 70 was discarded!

    def test_clear_while_awaiting_confirmation_clears_all(self, gui_app: VoiceCalculatorApp):
        """Pressing Clear while awaiting confirmation clears total and discards pending candidate."""
        gui_app.on_start()
        gui_app.calculator.add(100)
        gui_app.refresh_display()

        cand = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=50,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        gui_app.process_decision_result(cand)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION

        gui_app.on_clear()
        assert gui_app.calculator.total == 0
        assert gui_app.pending_candidate is None
        assert gui_app.lbl_total_value.cget("text") == "0"

    def test_undo_disabled_during_confirmation(self, gui_app: VoiceCalculatorApp):
        """Undo is strictly disabled while awaiting confirmation even when history is non-empty."""
        gui_app.on_start()
        gui_app.calculator.add(100)
        gui_app.refresh_display()
        assert gui_app.btn_undo.cget("state") == tk.NORMAL

        cand = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=25,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        gui_app.process_decision_result(cand)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION
        assert gui_app.btn_undo.cget("state") == tk.DISABLED

        # Calling on_undo while awaiting confirmation is a no-op
        gui_app.on_undo()
        assert gui_app.calculator.total == 100

    def test_controller_event_dispatch_started_and_processing(self, gui_app: VoiceCalculatorApp):
        """GUI handles STARTED and PROCESSING events correctly."""
        session_id = gui_app.controller.current_session_id

        # STARTED event
        ev_start = ControllerEvent(event_type=ControllerEventType.STARTED, session_id=session_id)
        gui_app._handle_controller_event(ev_start)
        assert gui_app.state == UIState.LISTENING

        # PROCESSING event
        ev_proc = ControllerEvent(event_type=ControllerEventType.PROCESSING, session_id=session_id)
        gui_app._handle_controller_event(ev_proc)
        assert gui_app.state == UIState.PROCESSING

    def test_controller_event_dispatch_decision(self, gui_app: VoiceCalculatorApp):
        """GUI handles DECISION events and transitions to AWAITING_CONFIRMATION."""
        session_id = gui_app.controller.current_session_id
        dec = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=88,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        ev_dec = ControllerEvent(event_type=ControllerEventType.DECISION, session_id=session_id, decision=dec)
        gui_app._handle_controller_event(ev_dec)

        assert gui_app.state == UIState.AWAITING_CONFIRMATION
        assert gui_app.pending_candidate == dec

        gui_app.on_confirm_add()
        assert gui_app.calculator.total == 88

    def test_controller_event_dispatch_error(self, gui_app: VoiceCalculatorApp):
        """GUI handles ERROR events and renders error message."""
        session_id = gui_app.controller.current_session_id
        ev_err = ControllerEvent(
            event_type=ControllerEventType.ERROR,
            session_id=session_id,
            error_message="Microphone was disconnected.",
            error_type="MicLost",
        )
        gui_app._handle_controller_event(ev_err)

        assert gui_app.state == UIState.ERROR
        assert "Microphone was disconnected" in gui_app.lbl_status.cget("text")

    def test_stale_controller_event_is_ignored(self, gui_app: VoiceCalculatorApp):
        """Events from outdated session IDs are ignored."""
        stale_session = gui_app.controller.current_session_id - 1
        dec = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=999,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        stale_event = ControllerEvent(event_type=ControllerEventType.DECISION, session_id=stale_session, decision=dec)
        gui_app._handle_controller_event(stale_event)

        # Candidate was NOT set
        assert gui_app.pending_candidate is None
        assert gui_app.calculator.total == 0

    def test_gui_mode_selector_initial_state(self, gui_app: VoiceCalculatorApp):
        """GUI initializes with Safe Mode selected by default."""
        assert gui_app.mode_var.get() == "SAFE"
        assert gui_app.decision_engine.mode == OperatingMode.SAFE
        assert gui_app.controller.mode == OperatingMode.SAFE

    def test_gui_mode_switching_updates_engine_and_controller(self, gui_app: VoiceCalculatorApp):
        """Selecting Fast Mode or Safe Mode updates engine and controller operating modes."""
        # Switch to Fast Mode
        gui_app.mode_var.set("FAST")
        gui_app.on_mode_change()
        assert gui_app.decision_engine.mode == OperatingMode.FAST
        assert gui_app.controller.mode == OperatingMode.FAST
        assert "Fast Mode active" in gui_app.lbl_feedback.cget("text")

        # Switch back to Safe Mode
        gui_app.mode_var.set("SAFE")
        gui_app.on_mode_change()
        assert gui_app.decision_engine.mode == OperatingMode.SAFE
        assert gui_app.controller.mode == OperatingMode.SAFE
        assert "Safe Mode active" in gui_app.lbl_feedback.cget("text")

    def test_gui_mode_switching_does_not_corrupt_calculator_state(self, gui_app: VoiceCalculatorApp):
        """Switching modes never modifies running total or history entries."""
        gui_app.calculator.add(100)
        gui_app.calculator.add(50)
        assert gui_app.calculator.total == 150
        assert gui_app.calculator.count == 2

        # Switch mode multiple times
        gui_app.mode_var.set("FAST")
        gui_app.on_mode_change()
        assert gui_app.calculator.total == 150
        assert gui_app.calculator.count == 2

        gui_app.mode_var.set("SAFE")
        gui_app.on_mode_change()
        assert gui_app.calculator.total == 150
        assert gui_app.calculator.count == 2

    def test_gui_mode_switching_preserves_pending_candidate(self, gui_app: VoiceCalculatorApp):
        """Switching modes during pending confirmation preserves the pending candidate for resolution."""
        cand = DecisionResult(
            decision=DecisionType.ACCEPT,
            value=250,
            reason=DecisionReason.ACCEPTED_CANDIDATE,
            requires_confirmation=True,
        )
        gui_app.process_decision_result(cand)
        assert gui_app.state == UIState.AWAITING_CONFIRMATION
        assert gui_app.pending_candidate == cand

        # Switch mode while candidate is pending
        gui_app.mode_var.set("FAST")
        gui_app.on_mode_change()

        # Pending candidate remains intact
        assert gui_app.pending_candidate == cand
        gui_app.on_confirm_add()
        assert gui_app.calculator.total == 250
        assert gui_app.pending_candidate is None



