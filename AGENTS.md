# AGENTS.md — Voice Calculator

## 1. Project Identity

This repository contains **Voice Calculator**, an offline Windows desktop application designed to continuously recognize spoken English numbers and add them to a running total.

This is a **specialized voice calculator**, not a voice assistant.

The primary engineering objective is:

> **Prevent incorrect numbers from being silently added.**

Correctness and reliability take priority over convenience, visual complexity, and raw recognition speed.

---

# 2. Source of Truth

Before making meaningful changes, inspect the relevant project documentation.

Required documents:

* `docs/prd.md` — product requirements
* `docs/architecture.md` — technical architecture
* `docs/rules.md` — engineering and coding rules
* `docs/phases.md` — implementation roadmap
* `docs/design.md` — UI/UX requirements
* `docs/memory.md` — current project state
* `docs/research.md` — experiments and evidence

### Priority order

When information conflicts, use this order:

1. Explicit user instruction in the current task
2. `docs/prd.md`
3. `docs/architecture.md`
4. `docs/rules.md`
5. `docs/phases.md`
6. `docs/design.md`
7. `docs/memory.md`
8. `docs/research.md`
9. Existing implementation

If a conflict cannot be resolved safely, stop and report it rather than silently choosing an interpretation.

---

# 3. Core Product Rules

These requirements must never be violated without explicit approval.

### Speech

* English speech only.
* Supported number range: **0–2000**.
* Continuous listening is required while listening mode is active.
* Start and Stop are physical GUI interactions.
* **Never implement voice commands.**
* Do not interpret words such as "start", "stop", "clear", "undo", or "reset" as commands.

### Calculation

* Addition only.
* Arithmetic must be deterministic.
* Never use an LLM for arithmetic.
* Never use an LLM as the authoritative number parser.
* Never silently add an uncertain recognition.

### Offline

* Normal application operation must not require internet access.
* Do not send microphone audio, recognized speech, calculations, or business information to external services.
* Do not add telemetry without explicit approval.

### Reliability

A false addition is more serious than requesting repetition.

When recognition is uncertain, the application must:

* request confirmation, or
* request repetition, or
* safely reject the input.

It must not silently guess.

---

# 4. Coding-Agent Behavior

## Before coding

Always:

1. Inspect the repository.
2. Check the current Git status.
3. Read `AGENTS.md`.
4. Read the documentation relevant to the requested task.
5. Read `docs/memory.md`.
6. Inspect existing implementations before creating new ones.
7. Identify the smallest set of files that need modification.

Do not immediately start generating code.

---

# 5. Work One Task at a Time

Implement **only the task explicitly requested**.

Do not:

* implement future phases,
* redesign unrelated modules,
* add speculative features,
* refactor working code unnecessarily,
* replace dependencies without evidence,
* rewrite large sections merely for style,
* create abstractions that are not currently required.

If you notice an improvement outside the current task, document it as a suggestion instead of implementing it automatically.

---

# 6. Phase Discipline

Follow `docs/phases.md`.

A phase is not complete merely because code exists.

A phase is complete only when:

* implementation is finished,
* relevant tests have been run,
* acceptance criteria are satisfied,
* failures have been addressed or documented,
* `docs/memory.md` is updated.

Do not automatically begin the next phase.

**Stop at the requested task boundary.**

---

# 7. Testing Rules

Testing is mandatory.

Never claim:

* "tests pass",
* "verified",
* "working",
* "accurate",
* "production-ready",

unless the relevant verification was actually performed.

### Bug fixes

Whenever practical:

> Every bug fix must include a regression test.

### Never weaken tests

Do not:

* delete failing tests,
* loosen assertions just to make them pass,
* skip tests without documenting why,
* replace a meaningful test with a trivial one.

If a test exposes a legitimate design problem, investigate the underlying problem.

---

# 8. Speech Recognition Rules

ASR model selection must be evidence-based.

Potential models may include:

* Vosk
* faster-whisper
* other suitable offline ASR systems

Do not assume that a model is better because it is newer, larger, or popular.

Do not claim an accuracy percentage without benchmark evidence.

Do not introduce a second ASR model merely because it sounds theoretically safer.

The ASR architecture must remain modular so that models can be replaced without rewriting the entire application.

Confidence scores are **signals, not guarantees**.

---

# 9. Number Parser Rules

The number parser must be deterministic.

It must:

* support the documented English number grammar,
* support 0–2000,
* reject malformed structures,
* reject unsupported words,
* reject out-of-range values,
* never silently guess the user's intended number.

Do not use an LLM, generative model, or probabilistic reasoning for number parsing.

Examples of potentially invalid structures such as:

```text
one twenty
five thousand
twelve hundred fifty-seven
```

must be handled according to the documented grammar rather than guessed.

The accepted linguistic forms must be defined in `docs/prd.md` and/or `docs/architecture.md`.

---

# 10. Audio and GUI Separation

The GUI must remain responsive.

Do not perform long-running operations directly on the GUI thread.

Audio capture, VAD, ASR inference, and other blocking operations must be designed so they do not freeze the interface.

GUI updates must occur through the appropriate GUI-safe mechanism.

Do not introduce concurrency merely for complexity. Use it when required for responsiveness or continuous listening.

---

# 11. Dependencies

Before adding a dependency:

1. Determine whether the standard library or existing dependency can solve the problem.
2. Explain why the new dependency is required.
3. Verify Windows compatibility.
4. Consider offline operation.
5. Consider package size and installation complexity.
6. Consider maintenance risk.

Do not add libraries simply because they are convenient.

---

# 12. Security and Privacy

Treat microphone data as sensitive application input.

Never:

* upload audio,
* call external speech APIs,
* transmit business data,
* add hidden telemetry,
* embed API keys,
* commit credentials,
* store unnecessary raw audio.

Use local processing wherever possible.

If recording audio becomes necessary for a research or benchmark task, make the recording process explicit and document it.

---

# 13. Research and Benchmarking

Experimental decisions must be recorded in:

`docs/research.md`

Examples:

* Vosk with grammar vs without grammar.
* Vosk vs faster-whisper.
* Different VAD settings.
* Confidence threshold calibration.
* Recognition of confusable numbers.
* Latency measurements.
* Resource usage.
* Long-session stability.

Never fabricate benchmark results.

Distinguish clearly between:

* measured result,
* hypothesis,
* recommendation,
* assumption,
* pending experiment.

Architecture decisions based on experiments should be reflected in `docs/architecture.md`.

---

# 14. Documentation Maintenance

After meaningful implementation work:

### Update `docs/memory.md`

Record:

* current phase,
* completed task,
* files changed,
* tests performed,
* actual results,
* known issues,
* decisions made,
* next task.

### Update `docs/research.md`

Only when research, benchmarking, calibration, or experimentation occurred.

Do not fill either document with invented information.

---

# 15. Git Discipline

Use small, meaningful commits.

Good examples:

```text
feat(parser): implement number grammar
test(parser): add boundary number tests
feat(audio): add microphone capture
feat(vad): add utterance segmentation
test(asr): add prerecorded benchmark
fix(parser): reject invalid number structures
```

Avoid giant commits containing unrelated work.

Do not commit:

* virtual environments,
* generated logs,
* raw audio recordings,
* model binaries,
* caches,
* secrets,
* temporary files,

unless explicitly required.

---

# 16. Architecture Changes

Do not silently change architecture.

If the implementation reveals that the documented architecture is inadequate:

1. Identify the problem.
2. Explain the proposed change.
3. Determine which documentation is affected.
4. Make the smallest justified change.
5. Update the relevant documentation.
6. Record the decision in `docs/memory.md`.
7. Record experimental evidence in `docs/research.md` when applicable.

Do not perform large architectural rewrites during an unrelated task.

---

# 17. Error Handling

Errors must fail safely.

The application should never convert:

```text
ASR failure
microphone failure
parser failure
VAD failure
unexpected exception
```

into an arbitrary number.

If the system cannot safely determine a number:

> Do not add anything.

Instead, communicate the problem clearly and allow the user to retry.

---

# 18. Accuracy Claims

Never use vague claims such as:

> "The model is highly accurate."

Prefer measurable statements such as:

> "On the current evaluation dataset, exact integer accuracy was X%."

Only report measured results.

Do not treat generic model benchmarks as proof of performance for this application.

The actual target user and intended operating environment are the primary validation environment.

---

# 19. Credit and Time Efficiency

AI coding-agent usage is limited.

Optimize every task for useful progress.

Prefer:

* small tasks,
* focused prompts,
* targeted file changes,
* existing libraries,
* existing working code,
* fast deterministic tests,
* incremental validation.

Avoid:

* massive prompts,
* rebuilding working modules,
* unnecessary refactoring,
* speculative features,
* repeated explanations of the entire project,
* implementing multiple phases at once.

The coding agent should use the repository documentation as persistent context rather than requiring the entire project specification to be pasted into every prompt.

---

# 20. Completion Report

At the end of every task, provide:

```text
TASK COMPLETED
==============

Task:
[What was requested]

Implemented:
- [item]
- [item]

Files changed:
- [file]
- [file]

Tests run:
- [test/command]

Results:
- [actual result]

Acceptance criteria:
- [PASS/FAIL] criterion
- [PASS/FAIL] criterion

Known issues:
- [issue or "None"]

Documentation updated:
- [file]

Recommended next task:
- [next small task]

STOP
```

Do not begin the recommended next task automatically.

---

# 21. Final Principle

The project is not judged by how much code has been generated.

It is judged by whether it can reliably perform this simple operation:

> User speaks a number → system correctly understands it → system safely adds it.

When uncertain:

> **Repeat is better than a wrong total.**

When in doubt:

> **Measure before deciding.**

When a task is complete:

> **Test, document, stop.**
