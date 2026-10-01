"""Desktop GUI for Voice Calculator with background ListeningController integration.

Implements the Tkinter desktop user interface per docs/design.md:
- Prominent running total hero display.
- Physical Start and Stop controls integrated with background ListeningController.
- Explicit visual status indicators (Stopped, Listening, Processing, Awaiting Confirmation, Repeat, Error).
- Non-blocking polling event loop via Tkinter after() delivering background worker events.
- History view showing ordered accepted additions and resulting totals.
- Undo and Clear/Reset operations.
- Candidate confirmation area (Add / Discard).
- Pure UI separation from audio, ASR, and safety policies.
"""

import logging
import queue
import tkinter as tk
from tkinter import ttk
from typing import Optional

from voice_calculator.calculator import Calculator, HistoryEntry
from voice_calculator.controller import ControllerEvent, ControllerEventType, ListeningController
from voice_calculator.decision import (
    DecisionReason,
    DecisionResult,
    DecisionType,
    SafetyDecisionEngine,
)
from voice_calculator.gui.messages import (
    STATE_COLORS,
    STATE_TEXTS,
    UIState,
    format_number,
    get_decision_feedback_message,
)
from voice_calculator.pipeline import PipelineResult

logger = logging.getLogger("voice_calculator.gui")


class VoiceCalculatorApp:
    """Tkinter Desktop Application for Voice Calculator."""

    def __init__(
        self,
        root: Optional[tk.Tk] = None,
        calculator: Optional[Calculator] = None,
        decision_engine: Optional[SafetyDecisionEngine] = None,
        controller: Optional[ListeningController] = None,
    ) -> None:
        self.root = root or tk.Tk()
        self.calculator = calculator or Calculator()
        self.decision_engine = decision_engine or SafetyDecisionEngine()
        self.controller = controller or ListeningController(decision_engine=self.decision_engine)

        self.state: UIState = UIState.STOPPED
        self.pending_candidate: Optional[DecisionResult] = None
        self._poll_job: Optional[str] = None
        self._is_closing: bool = False

        self._init_window()
        self._create_widgets()
        self._bind_shortcuts()
        self.refresh_display()
        self._start_event_polling()

    def _init_window(self) -> None:
        self.root.title("Voice Calculator")
        self.root.minsize(700, 520)
        self.root.geometry("850x620")
        self.root.configure(bg="#f4f6f8")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _create_widgets(self) -> None:
        # Main layout container
        main_frame = tk.Frame(self.root, bg="#f4f6f8", padx=20, pady=16)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Total Hero Area
        total_card = tk.Frame(main_frame, bg="#ffffff", bd=1, relief=tk.SOLID, padx=16, pady=12)
        total_card.pack(fill=tk.X, pady=(0, 10))

        lbl_total_title = tk.Label(
            total_card,
            text="TOTAL",
            font=("Segoe UI", 12, "bold"),
            fg="#546e7a",
            bg="#ffffff",
        )
        lbl_total_title.pack(anchor=tk.W)

        self.lbl_total_value = tk.Label(
            total_card,
            text="0",
            font=("Segoe UI", 56, "bold"),
            fg="#1a237e",
            bg="#ffffff",
        )
        self.lbl_total_value.pack(anchor=tk.CENTER, pady=4)

        # 2. Status Indicator Bar
        self.status_bar_frame = tk.Frame(main_frame, bg=STATE_COLORS[UIState.STOPPED], padx=12, pady=8)
        self.status_bar_frame.pack(fill=tk.X, pady=(0, 10))

        self.lbl_status = tk.Label(
            self.status_bar_frame,
            text=STATE_TEXTS[UIState.STOPPED],
            font=("Segoe UI", 13, "bold"),
            fg="#ffffff",
            bg=STATE_COLORS[UIState.STOPPED],
        )
        self.lbl_status.pack(anchor=tk.CENTER)

        # 3. Confirmation & Feedback Area
        self.feedback_card = tk.Frame(main_frame, bg="#ffffff", bd=1, relief=tk.SOLID, padx=16, pady=10)
        self.feedback_card.pack(fill=tk.X, pady=(0, 10))

        self.lbl_feedback = tk.Label(
            self.feedback_card,
            text="Ready — press Start to begin listening.",
            font=("Segoe UI", 14),
            fg="#263238",
            bg="#ffffff",
        )
        self.lbl_feedback.pack(pady=(0, 6))

        # Confirmation action buttons frame (hidden by default)
        self.confirm_buttons_frame = tk.Frame(self.feedback_card, bg="#ffffff")

        self.btn_confirm_add = tk.Button(
            self.confirm_buttons_frame,
            text="Add (Enter)",
            font=("Segoe UI", 13, "bold"),
            bg="#2e7d32",
            fg="#ffffff",
            activebackground="#1b5e20",
            activeforeground="#ffffff",
            padx=16,
            pady=6,
            command=self.on_confirm_add,
        )
        self.btn_confirm_add.pack(side=tk.LEFT, padx=8)

        self.btn_confirm_discard = tk.Button(
            self.confirm_buttons_frame,
            text="Discard (Esc)",
            font=("Segoe UI", 13, "bold"),
            bg="#78909c",
            fg="#ffffff",
            activebackground="#546e7a",
            activeforeground="#ffffff",
            padx=16,
            pady=6,
            command=self.on_confirm_discard,
        )
        self.btn_confirm_discard.pack(side=tk.LEFT, padx=8)

        # 4. Physical Controls Row
        controls_frame = tk.Frame(main_frame, bg="#f4f6f8")
        controls_frame.pack(fill=tk.X, pady=(0, 10))

        self.btn_start = tk.Button(
            controls_frame,
            text="▶ START",
            font=("Segoe UI", 13, "bold"),
            bg="#2e7d32",
            fg="#ffffff",
            activebackground="#1b5e20",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            command=self.on_start,
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = tk.Button(
            controls_frame,
            text="⏹ STOP",
            font=("Segoe UI", 13, "bold"),
            bg="#c62828",
            fg="#ffffff",
            activebackground="#b71c1c",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            state=tk.DISABLED,
            command=self.on_stop,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=8)

        self.btn_undo = tk.Button(
            controls_frame,
            text="↶ UNDO (Ctrl+Z)",
            font=("Segoe UI", 13, "bold"),
            bg="#455a64",
            fg="#ffffff",
            activebackground="#37474f",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            state=tk.DISABLED,
            command=self.on_undo,
        )
        self.btn_undo.pack(side=tk.LEFT, padx=8)

        self.btn_clear = tk.Button(
            controls_frame,
            text="🗑 CLEAR",
            font=("Segoe UI", 13, "bold"),
            bg="#78909c",
            fg="#ffffff",
            activebackground="#546e7a",
            activeforeground="#ffffff",
            padx=18,
            pady=8,
            command=self.on_clear,
        )
        self.btn_clear.pack(side=tk.RIGHT, padx=(8, 0))

        # 5. History / Recent Entries Area
        history_frame = tk.Frame(main_frame, bg="#ffffff", bd=1, relief=tk.SOLID, padx=12, pady=8)
        history_frame.pack(fill=tk.BOTH, expand=True)

        lbl_history_title = tk.Label(
            history_frame,
            text="RECENT ADDITIONS",
            font=("Segoe UI", 11, "bold"),
            fg="#546e7a",
            bg="#ffffff",
        )
        lbl_history_title.pack(anchor=tk.W, pady=(0, 4))

        # Scrollable list for history
        list_container = tk.Frame(history_frame, bg="#ffffff")
        list_container.pack(fill=tk.BOTH, expand=True)

        self.scrollbar = tk.Scrollbar(list_container)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.history_listbox = tk.Listbox(
            list_container,
            font=("Segoe UI", 12),
            fg="#263238",
            bg="#ffffff",
            selectbackground="#cfd8dc",
            selectforeground="#000000",
            bd=0,
            highlightthickness=0,
            yscrollcommand=self.scrollbar.set,
        )
        self.history_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.config(command=self.history_listbox.yview)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Return>", lambda e: self.on_confirm_add())
        self.root.bind("<KP_Enter>", lambda e: self.on_confirm_add())
        self.root.bind("<Escape>", lambda e: self.on_confirm_discard())
        self.root.bind("<Control-z>", lambda e: self.on_undo())
        self.root.bind("<Control-Z>", lambda e: self.on_undo())

    def _start_event_polling(self) -> None:
        """Starts periodic event queue polling on the Tkinter main thread."""
        self._poll_controller_events()

    def _poll_controller_events(self) -> None:
        """Drains background worker events and dispatches GUI updates on main thread."""
        if self._is_closing:
            return

        try:
            while True:
                event = self.controller.event_queue.get_nowait()
                self._handle_controller_event(event)
        except queue.Empty:
            pass
        except Exception as e:
            logger.error("Error processing controller event: %s", e)

        # Reschedule next poll
        if not self._is_closing:
            try:
                self._poll_job = self.root.after(50, self._poll_controller_events)
            except Exception:
                pass

    def _handle_controller_event(self, event: ControllerEvent) -> None:
        """Handles a single event delivered from ListeningController."""
        # Filter out stale events from previous sessions
        if event.session_id != self.controller.current_session_id and event.event_type != ControllerEventType.STOPPED:
            logger.debug("Discarding stale event from session %d (current=%d)", event.session_id, self.controller.current_session_id)
            return

        logger.debug("GUI received event: %s (session=%d)", event.event_type, event.session_id)

        if event.event_type == ControllerEventType.STARTED:
            self.set_state(UIState.LISTENING)
            self.lbl_feedback.configure(text="Listening — speak a number between 0 and 2,000.")
            self.confirm_buttons_frame.pack_forget()

        elif event.event_type == ControllerEventType.PROCESSING:
            self.set_state(UIState.PROCESSING)
            self.lbl_feedback.configure(text="Working it out…")

        elif event.event_type == ControllerEventType.DECISION:
            if event.decision is not None:
                self.process_decision_result(event.decision)

        elif event.event_type == ControllerEventType.STOPPED:
            self.set_state(UIState.STOPPED)
            self.lbl_feedback.configure(text="Stopped — press Start to listen.")

        elif event.event_type == ControllerEventType.ERROR:
            err_msg = event.error_message or "An unexpected error occurred."
            self.set_state(UIState.ERROR, custom_text=err_msg)
            self.lbl_feedback.configure(text=err_msg)

    def set_state(self, new_state: UIState, custom_text: Optional[str] = None) -> None:
        """Updates the high-level GUI state and refreshes indicators."""
        self.state = new_state
        color = STATE_COLORS.get(new_state, "#555555")
        text = custom_text or STATE_TEXTS.get(new_state, "")

        self.status_bar_frame.configure(bg=color)
        self.lbl_status.configure(text=text, bg=color)

        # Control button states
        if self.state == UIState.STOPPED or self.state == UIState.ERROR:
            self.btn_start.configure(state=tk.NORMAL)
            self.btn_stop.configure(state=tk.DISABLED)
        else:
            self.btn_start.configure(state=tk.DISABLED)
            self.btn_stop.configure(state=tk.NORMAL)

        # Undo is disabled during confirmation or if history is empty
        if self.state == UIState.AWAITING_CONFIRMATION or self.calculator.is_empty:
            self.btn_undo.configure(state=tk.DISABLED)
        else:
            self.btn_undo.configure(state=tk.NORMAL)

    def on_start(self) -> None:
        """Handles physical Start button click."""
        logger.info("GUI Start clicked: starting listening controller.")
        self.set_state(UIState.LISTENING, custom_text="Starting microphone…")
        self.lbl_feedback.configure(text="Starting microphone…")
        self.confirm_buttons_frame.pack_forget()

        started = self.controller.start()
        if not started and not self.controller.is_listening:
            self.set_state(UIState.ERROR, custom_text="Could not start listening.")
            self.lbl_feedback.configure(text="Could not initialize microphone or speech engine.")

    def on_stop(self) -> None:
        """Handles physical Stop button click."""
        logger.info("GUI Stop clicked: stopping listening controller.")
        if self.pending_candidate is not None:
            logger.info("Discarding pending candidate on Stop.")
            self.pending_candidate = None
            self.confirm_buttons_frame.pack_forget()

        self.controller.stop()
        self.set_state(UIState.STOPPED)
        self.lbl_feedback.configure(text="Stopped — press Start to listen.")

    def on_undo(self) -> None:
        """Handles Undo button click or Ctrl+Z shortcut."""
        if self.state == UIState.AWAITING_CONFIRMATION:
            logger.debug("Undo ignored during pending confirmation.")
            return

        removed = self.calculator.undo()
        if removed is not None:
            self.lbl_feedback.configure(text=f"Undone: -{format_number(removed.value)}")
        else:
            self.lbl_feedback.configure(text="Nothing to undo.")

        self.refresh_display()

    def on_clear(self) -> None:
        """Handles Clear / Reset button click."""
        if self.pending_candidate is not None:
            self.pending_candidate = None
            self.confirm_buttons_frame.pack_forget()

        self.calculator.reset()
        self.lbl_feedback.configure(text="Total cleared.")
        self.refresh_display()
        if self.state == UIState.AWAITING_CONFIRMATION:
            if self.controller.is_listening:
                self.set_state(UIState.LISTENING)
            else:
                self.set_state(UIState.STOPPED)

    def on_confirm_add(self) -> None:
        """Confirms adding the currently pending candidate."""
        if self.state != UIState.AWAITING_CONFIRMATION or self.pending_candidate is None:
            return

        cand = self.pending_candidate
        self.pending_candidate = None
        self.confirm_buttons_frame.pack_forget()

        if cand.value is not None:
            self.calculator.add(cand.value)
            self.lbl_feedback.configure(text=f"Added: +{format_number(cand.value)}")
            logger.info("Confirmed addition of %d (new total=%d)", cand.value, self.calculator.total)

        self.refresh_display()
        if self.controller.is_listening:
            self.set_state(UIState.LISTENING)
        else:
            self.set_state(UIState.STOPPED)

    def on_confirm_discard(self) -> None:
        """Discards the currently pending candidate."""
        if self.state != UIState.AWAITING_CONFIRMATION or self.pending_candidate is None:
            return

        cand = self.pending_candidate
        self.pending_candidate = None
        self.confirm_buttons_frame.pack_forget()

        self.lbl_feedback.configure(text=f"Discarded: {format_number(cand.value)}")
        logger.info("Discarded candidate %s", cand.value)

        self.refresh_display()
        if self.controller.is_listening:
            self.set_state(UIState.LISTENING)
        else:
            self.set_state(UIState.STOPPED)

    def process_pipeline_result(self, pipeline_result: PipelineResult) -> DecisionResult:
        """Evaluates a raw PipelineResult through safety engine and updates GUI."""
        decision_result = self.decision_engine.evaluate(pipeline_result)
        self.process_decision_result(decision_result)
        return decision_result

    def process_decision_result(self, decision_result: DecisionResult) -> None:
        """Applies a DecisionResult to GUI and calculator state."""
        # 1. Candidate ACCEPT
        if decision_result.decision == DecisionType.ACCEPT:
            if decision_result.requires_confirmation:
                self.pending_candidate = decision_result
                formatted_val = format_number(decision_result.value)
                self.lbl_feedback.configure(text=f"Did you say:  {formatted_val}  ?")
                self.btn_confirm_add.configure(text=f"Add {formatted_val} (Enter)")
                self.confirm_buttons_frame.pack(pady=(4, 0))
                self.set_state(UIState.AWAITING_CONFIRMATION)
            else:
                # Auto-add candidate if policy allows
                if decision_result.value is not None:
                    self.calculator.add(decision_result.value)
                    self.lbl_feedback.configure(text=f"Added: +{format_number(decision_result.value)}")
                self.refresh_display()
                if self.controller.is_listening:
                    self.set_state(UIState.LISTENING)
                else:
                    self.set_state(UIState.STOPPED)

        # 2. REPEAT required
        elif decision_result.decision == DecisionType.REPEAT:
            msg = get_decision_feedback_message(decision_result)
            self.lbl_feedback.configure(text=msg)
            self.set_state(UIState.REPEAT_REQUIRED, custom_text=msg)

        # 3. REJECT
        elif decision_result.decision == DecisionType.REJECT:
            msg = get_decision_feedback_message(decision_result)
            self.lbl_feedback.configure(text=msg)
            self.set_state(UIState.REPEAT_REQUIRED, custom_text=msg)

    def refresh_display(self) -> None:
        """Refreshes total value, Undo button state, and recent additions list."""
        # Total value
        self.lbl_total_value.configure(text=format_number(self.calculator.total))

        # Undo button state
        if self.state == UIState.AWAITING_CONFIRMATION or self.calculator.is_empty:
            self.btn_undo.configure(state=tk.DISABLED)
        else:
            self.btn_undo.configure(state=tk.NORMAL)

        # Refresh history list (newest on top)
        self.history_listbox.delete(0, tk.END)
        entries = self.calculator.history
        for entry in reversed(entries):
            line = f"#{entry.sequence:<4} +{format_number(entry.value):<8}  Total: {format_number(entry.running_total)}"
            self.history_listbox.insert(tk.END, line)

    def on_close(self) -> None:
        """Handles window close event with clean background worker shutdown."""
        logger.info("Application closing: shutting down ListeningController.")
        self._is_closing = True
        if self._poll_job is not None:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass

        self.controller.stop(timeout=1.0)
        try:
            self.root.destroy()
        except Exception:
            pass
