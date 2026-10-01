# Rules — Coding Agent Constitution

> These rules bind any AI coding agent (Antigravity, Zcode, or other) working on this repo. They override convenience. If a rule conflicts with a user prompt, **stop and ask**, quoting the rule.
> Docs: `prd.md` (what), `architecture.md` (how), `phases.md` (order), `design.md` (UI), `memory.md` (progress), `research.md` (evidence).

---

## A. Start-of-Task Protocol (read little, read the right things)

1. Read `memory.md` first (current phase, current task, constraints).
2. Read **only** the doc sections the task names (e.g. "prd.md §7", "architecture.md §9"). Do not re-read everything every time.
3. Inspect existing code in the files you will touch before editing (`ls`, open the modules, run existing tests). Never assume what exists.
4. Confirm the task belongs to the **current phase** in `phases.md`. If not, stop and report.

## B. Scope Discipline

5. **Implement only the current phase and only the requested subtask.** Never generate the whole application in one task.
6. **Stop at the phase/subtask boundary** and report using the format in §H. Do not start the next task "to be helpful".
7. Do not rewrite, reformat, or refactor working modules unless the task explicitly requires it. Prefer the smallest diff that satisfies the acceptance criteria.
8. No speculative abstractions: no plugin systems, registries, base-class hierarchies, or config frameworks beyond what `architecture.md` specifies.
9. Do not create files outside the layout in `architecture.md` §4 without stating why in the report.
10. Do not implement items listed under Non-Goals or Future Enhancements in `prd.md`.

## C. Non-Negotiable Product Rules (FIXED)

11. **Never use an LLM, or any ML model, for number parsing or arithmetic.** Parsing = deterministic code in `numparse.py`; arithmetic = `calculator.py`.
12. **Never silently add an uncertain recognition.** Anything uncertain → CONFIRM or REJECT. ASR confidence is never proof of correctness.
13. **Never introduce voice commands** (undo, stop, yes/no, clear, confirm, etc.). All control is via physical GUI buttons/keys. Non-number speech is rejected.
14. **Addition only.** No other operators.
15. **Parser must reject, not guess.** Unknown/ambiguous/out-of-range input returns a rejection reason.
16. **Keep audio processing off the GUI thread.** Never call Tk from non-GUI threads.
17. **Do not upload audio or business data anywhere.** No network calls in application code. No telemetry. Disable library auto-downloads; use local model paths.
18. Do not save raw audio or log transcripts/values by default (see `architecture.md` §13).
19. The calculator's total must stay derived from entries; no second source of truth.

## D. Change Control

20. **Never change requirements or architecture silently.** If a change is needed: state the reason, edit the relevant doc (`prd.md`/`architecture.md`/`design.md`), and record it in `memory.md` → "Confirmed decisions". User approval is required for changes to anything labeled FIXED.
21. **Never add a dependency without justification.** Before adding: check whether stdlib/existing deps suffice; record package, version, purpose, size/weight, alternative considered in `memory.md`. Pin versions in `requirements.txt` (or equivalent).
22. Do not change tunable thresholds to make tests or benchmarks pass. Thresholds change only with recorded evidence in `research.md`.
23. Items listed in `memory.md` → "Do not change casually" require explicit user approval to modify.

## E. Testing and Honesty

24. **Never claim tests passed unless you actually ran them** in this session and saw the output. Paste the command and a short result summary (counts). If you could not run them, say so plainly.
25. **Do not invent benchmark results, accuracy numbers, latency figures, or thresholds.** Missing data is reported as "not measured".
26. **Every bug fix includes a regression test** where applicable (state when not applicable and why).
27. New logic in `numparse`, `decision`, `calculator`, `state` requires unit tests in the same task.
28. Tests must be deterministic, offline, fast, and independent of microphone hardware (use recorded fixtures or fakes). Hardware-dependent checks are documented as manual tests.
29. Never delete or weaken a test to make it pass. If a test is wrong, explain and fix it with justification.
30. Do not report a task as done if acceptance criteria in `phases.md` are unmet; report what remains.

## F. Records and Git

31. **Update `memory.md` after each meaningful task** (status, completed work, files changed, test status, next task, new decisions/bugs/lessons). Keep entries concise; replace stale text rather than appending forever.
32. **Update `research.md` after experiments** (use the templates; real numbers only, with dataset and settings).
33. **Small, meaningful Git commits**: one logical change per commit, imperative message (e.g. `Add strict number parser for 0-2000`). Reference the phase/subtask. Do not commit broken tests.
34. Never commit: model files, raw recordings, logs, virtual environments, `__pycache__`, build outputs, personal data. Maintain `.gitignore` accordingly (Phase 0). Small synthetic test fixtures explicitly approved in a task may be committed.
35. Do not force-push, rewrite history, or delete branches unless asked.

## G. Code Quality

36. Python 3.11+ style, type hints on public functions, short docstrings stating contract (not narration).
37. Constants and tunables live in `config.py` only. No magic numbers in logic.
38. Errors: catch specific exceptions; surface user-facing failures through the typed errors in `architecture.md` §12; never swallow exceptions silently.
39. Keep functions small and pure where possible. No global mutable state outside the controller.
40. Windows-first: use `pathlib`; avoid POSIX-only calls; no shell-specific assumptions in code.
41. User-facing text lives in one place (`gui/messages.py` or a constants block) so wording is consistent with `design.md`.

## H. Task-Completion Report (mandatory, concise, ≤ ~25 lines)

```
## Task Report
Phase/Subtask: <e.g., 1.2>
Goal: <one line>
Status: DONE | PARTIAL | BLOCKED
Files changed: <list, with new/modified>
What I did: <3-6 bullets>
Tests run: <exact command> -> <passed/failed counts>   (or "NOT RUN: reason")
Acceptance criteria: <each criterion: met / not met / not measured>
Dependencies added: <none | package + justification>
Docs updated: <memory.md / research.md / others>
Commit(s): <hash + message | not committed>
Deviations from docs: <none | description + reason>
Open issues / risks: <bullets or none>
Next suggested task: <one line; do not start it>
```

## I. Escalation: Stop and Ask When

- A requirement is ambiguous and the answer affects correctness.
- A task needs a FIXED requirement changed.
- Tests fail and the fix would require changing scope.
- You are about to exceed the task's scope or touch many unrelated files.
- Credits/context are running low: stop at a clean state (tests passing, memory.md updated) and report.

## J. Quick Self-Check Before Reporting

- Did I stay in the current subtask? Any voice command, LLM use, or silent add? Any network use?
- Did I run the tests and report real output? Did I update `memory.md`? Is the commit small and clean?
