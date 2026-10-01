# Design — UI/UX

> Doc role: user-facing behavior of the MVP. Requirements: `prd.md` (FR-6…FR-15, §8–9). Threading and state machine: `architecture.md` §6, §11. Build order: `phases.md` Phase 7.
> Scope guard: one window, no menus, no settings screen, no navigation, no animations beyond simple color/text changes. Anything not listed here is not in the MVP.
> Sizes below are **DEFAULT** starting values; adjust only for readability, and record changes in `memory.md`.

---

## 1. Design Principles

1. **The total is the hero.** Largest element, always visible, never obscured.
2. **State is never ambiguous.** The user can always tell whether the app is listening, thinking, waiting for them, or broken.
3. **Ask rather than guess.** Uncertainty is shown as a question with two clear buttons, not as an error.
4. **Plain language.** No technical terms (no "ASR", "VAD", "confidence", "exception").
5. **Few controls, big targets.** Every control is a physical button or key; no voice control.
6. **Safe actions are easy, destructive actions are deliberate.** Undo is one click; Reset needs a dialog.
7. **Never lose the total.** Errors never clear it.

## 2. Main Screen Layout

Single resizable window (DEFAULT 900×650 min 700×520). Top to bottom:

1. **Total area** — label "Total" (small) and the running total (very large).
2. **Status bar** — colored indicator + one-line status text.
3. **Last number / confirmation area** — shows "Last added: 150" normally; becomes the confirmation prompt when needed (§6).
4. **Control row** — **Start**, **Stop**, **Undo**, **Reset**.
5. **Recent entries list** — scrollable, newest at top.

## 3. Visual Hierarchy

| Priority | Element | Default size/style |
|----------|---------|--------------------|
| 1 | Running total | ~96 pt bold, high-contrast, thousands separators (e.g. `12,450`); shrinks in steps only if it would overflow |
| 2 | Status text + indicator | ~24 pt, color + text (never color alone) |
| 3 | Last number / confirmation prompt | ~36 pt number, ~20 pt text |
| 4 | Buttons | ≥ 20 pt label, min 56 px tall, min 140 px wide |
| 5 | Recent entries | ~18 pt, one per row |

Start is the primary button (strong color); Stop is clearly distinct; Reset is visually subdued (not red-and-prominent) and separated from Undo by spacing.

## 4. Status Indicators

Each state shows a color, a text, and (optionally) a simple symbol, so meaning never depends on color alone.

| State | Text | Color (DEFAULT) |
|-------|------|-----------------|
| Loading (app start) | "Loading, please wait…" | gray |
| IDLE | "Not listening — press Start" | gray |
| STARTING | "Starting microphone…" | amber |
| LISTENING | "Listening — say a number" | green |
| HEARING | "Hearing you…" | green (brighter) |
| PROCESSING | "Working it out…" | blue |
| AWAITING_CONFIRMATION | "Please check the number" | amber/orange |
| STOPPING | "Stopping…" | gray |
| ERROR | the specific message (§7) | red |

## 5. Listening and Processing Behavior

- **Start** enabled only in IDLE/ERROR and after models are loaded. **Stop** enabled in any listening/processing/confirming state; both are visibly disabled otherwise.
- Pressing Stop discards any in-flight utterance (nothing is added after Stop).
- After each result the status returns to "Listening — say a number" automatically.
- **ACCEPT** (only if enabled by policy): the entry appears in the list, the total updates, "Last added: N" shows briefly highlighted (DEFAULT ~1.5 s, color only, no animation).
- Processing shows "Working it out…"; if processing exceeds 3 s (PROVISIONAL), text becomes "Still working…"; the GUI stays responsive.
- During AWAITING_CONFIRMATION, listening is paused and the status says so.

## 6. Confirmation Flow

Triggered by a CONFIRM decision (default policy: every parsed number until auto-accept is validated).

```
 Did you say:   1 5 0   ?
 [  Add 150  (Enter) ]   [  Discard (Esc)  ]
```

- The interpreted number is shown **large**, with thousands separators.
- **Add** (default focus, key **Enter**) adds it, updates the total, returns to Listening.
- **Discard** (key **Esc**) drops it, returns to Listening, adds a "discarded" row in history.
- Nothing is added by timeout; the prompt waits indefinitely.
- Undo is disabled while confirming.
- Zero is always confirmed.
- No voice reply is accepted; speech while confirming is ignored (listening suspended).

## 7. Invalid Speech and Microphone/Processing Error Behavior

Messages (single source of truth; implement in `gui/messages.py`):

| Situation | Message | Behavior |
|-----------|---------|----------|
| Not a valid number / ambiguous / out of range | "Didn't catch that — please say the number again." (small gray line: what was heard, only when debug mode is on) | Nothing added; stays LISTENING; history row "not understood" |
| Out of range (>2000) | "That number is too large. I can add numbers up to 2000." | Same |
| Too quiet | "Too quiet — please speak a little louder." | Same |
| Too long / several numbers | "Please say one number at a time." | Same |
| Cut off / clipped | "That was cut off — please say it again." | Same |
| No microphone | "No microphone found. Plug in or enable a microphone, then press Start." | ERROR; total kept |
| Microphone busy/blocked | "The microphone can't be used. Check Windows microphone settings (Privacy → Microphone), then press Start." | ERROR |
| Microphone disconnected | "The microphone was disconnected. Listening has stopped. Your total is safe. Reconnect it and press Start." | ERROR |
| Model missing/failed | "A required speech file is missing. Please reinstall or contact the person who set this up." | Start disabled; Undo/Reset still work |
| Processing failed (single) | "Couldn't process that — please say it again." | Stays LISTENING |
| Repeated failures | "Listening stopped because of repeated problems. Your total is safe. Press Start to try again." | ERROR |
| Unexpected error | "Something went wrong. Your total is safe. Press Start to try again." | ERROR |

Rules: messages are calm, short, and always say what to do next; error banner never covers the total; errors never clear the total.

## 8. History and Undo Interaction

- Recent entries list: newest at top, shows `#N  value  status`, where status ∈ Added / Confirmed / Discarded / Not understood. Added/Confirmed rows are normal weight; Discarded/Not understood are gray and do not affect the total.
- Keep at least the last 20 rows visible via scrolling (full session history is retained in memory).
- **Undo** (button; key **Ctrl+Z**) removes the most recent *added* entry, subtracts it, and marks the row "Undone". Repeatable until nothing remains; disabled when there is nothing to undo or while confirming.
- After Undo the total updates immediately and status text is unchanged.
- No redo and no editing in MVP; to correct, Undo then speak again.

## 9. Reset Confirmation

- **Reset** opens a modal dialog: "Clear the total (12,450) and all N entries? This cannot be undone." Buttons: **Cancel** (default focus, Esc) and **Yes, clear everything**.
- Only the explicit second button clears. Enter on the default focus cancels.
- Reset is allowed while listening; listening continues after reset. If a confirmation is pending, it is cleared too.
- After reset: total `0`, list empty.

## 10. Accessibility and Readability

- High contrast (WCAG AA minimum for text); dark text on light background by default.
- Never rely on color alone; always text (and optionally symbol).
- Font sizes per §3; respect Windows display scaling.
- All actions reachable by keyboard: Tab order Start → Stop → Undo → Reset → list; Enter activates focused button; shortcuts Enter/Esc (confirmation), Ctrl+Z (Undo).
- No flashing or timed-disappearing critical information.
- Optional (OPEN, default off): audio beep on error. Not in MVP unless requested.

## 11. GUI Responsiveness Requirements

- The Tk main loop never runs recognition, VAD, capture, or model loading (`architecture.md` §11).
- Worker results arrive via queue, polled every ~50 ms.
- Button presses reflect within 100 ms (PROVISIONAL, `prd.md` NFR-3/AC-7).
- Closing the window while listening stops capture and exits cleanly within ~2 s; no orphan threads.
- Window resizing keeps the total readable (layout uses grid/pack with weights; no fixed-position hacks).

## 12. Text Wireframe

```
+--------------------------------------------------------------+
|  Voice Calculator                                            |
+--------------------------------------------------------------+
|  Total                                                       |
|                                                              |
|                       1 2 , 4 5 0                            |
|                                                              |
+--------------------------------------------------------------+
|  (●) Listening — say a number                                |
+--------------------------------------------------------------+
|  Last added: 150          [shown normally]                   |
|  ---- or, when CONFIRM ----                                  |
|  Did you say:  150 ?    [ Add 150 (Enter) ] [ Discard (Esc) ]|
+--------------------------------------------------------------+
|  [  START  ]  [  STOP  ]  [  UNDO  ]            [ Reset ]    |
+--------------------------------------------------------------+
|  Recent entries                                              |
|  #7   150     Added                                          |
|  #6   —       Not understood                                 |
|  #5   45      Confirmed                                      |
|  #4   1,000   Added                                          |
|  ...                                                         |
+--------------------------------------------------------------+
```

Error variant: the status bar turns red with the message from §7; the total area is unchanged.
