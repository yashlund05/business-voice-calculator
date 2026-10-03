"""Phase 6.1 (AC-7/AC-8): long-session soak test for Voice Calculator.

Runs the full production stack — real Tkinter GUI, ListeningController worker
thread, EnergyVAD segmentation, the default Vosk ASR engine, and the safety
decision engine — continuously for a configurable duration (default 60
minutes) while measuring:

- Crashes / unhandled exceptions (GUI callback and worker)
- Memory: process RSS (Windows WorkingSetSize) at start / 30 / 60 min + growth
  (AC-8: growth <= 50 MB)
- CPU: process CPU utilization sampled over the run (stability)
- Event queue depth (boundedness)
- GUI event-loop stall: max lateness of a 100 ms Tk after() probe (AC-7 <= 100 ms)
- Throughput: decisions processed vs utterances expected from the scripted
  source (missed-utterance proxy)

Audio input is a deterministic, real-time-paced loop of the local Dad
continuous recording (16 kHz mono PCM) — no microphone is opened and no audio
leaves the machine (privacy rules, AGENTS.md §12). A main-thread auto-responder
resolves pending confirmation candidates (mostly Add, some Discard, periodic
Undo) to exercise the full confirmation/recovery surface.

Usage (repo root):
    python tools/soak_test.py --duration-minutes 60
    python tools/soak_test.py --duration-minutes 3          # validation run
    python tools/soak_test.py --duration-minutes 5 --headless  # no GUI

Output: stdout summary + analysis/soak_samples.csv + analysis/soak_summary.json
"""

import argparse
import collections
import csv
import ctypes
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from voice_calculator.audio.capture import AudioFrame  # noqa: E402
from voice_calculator.audio.wavio import read_wav  # noqa: E402
from voice_calculator.config import (  # noqa: E402
    AUDIO_BLOCK_SAMPLES,
    AUDIO_BLOCK_DURATION_MS,
    AUDIO_SAMPLE_RATE,
)
from voice_calculator.controller import ControllerEventType, ListeningController  # noqa: E402

CONTINUOUS_WAV = PROJECT_ROOT / "data" / "processed_phone" / "dad_continuous_16k.wav"
SAMPLES_CSV = PROJECT_ROOT / "analysis" / "soak_samples.csv"
SUMMARY_JSON = PROJECT_ROOT / "analysis" / "soak_summary.json"


# --- Process memory (Windows, stdlib only) -----------------------------------

class _ProcessMemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def get_rss_mb() -> float | None:
    """Returns the process working set (RSS) in MB, or None if unavailable."""
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        psapi = ctypes.windll.psapi  # type: ignore[attr-defined]
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        pmc = _ProcessMemoryCounters()
        pmc.cb = ctypes.sizeof(_ProcessMemoryCounters)
        handle = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return pmc.WorkingSetSize / (1024.0 * 1024.0)
    except AttributeError:
        pass  # Non-Windows platform
    return None


# --- Instrumented event queue -------------------------------------------------

class CountingQueue(queue.Queue):
    """Event queue that counts ControllerEvents by type (GUI keeps consuming normally)."""

    def __init__(self) -> None:
        super().__init__()
        self.counts: collections.Counter = collections.Counter()

    def _count(self, item) -> None:
        event_type = getattr(item, "event_type", None)
        self.counts[event_type.name if event_type else "UNKNOWN"] += 1

    def put(self, item, block=True, timeout=None):  # type: ignore[override]
        self._count(item)
        return super().put(item, block=block, timeout=timeout)

    def put_nowait(self, item):  # type: ignore[override]
        self._count(item)
        return super().put_nowait(item)


# --- Scripted real-time audio source ------------------------------------------

class ScriptedSpeechSource:
    """AudioSource that loops a WAV file in real time (30 ms frames, wall-clock paced).

    Frames are delivered on the audio timeline: frame i is due at start + i*30ms.
    If processing ever falls behind, delivery lag grows — tracked as pace_lag_max.
    """

    def __init__(self, wav_path: Path, block_ms: int = AUDIO_BLOCK_DURATION_MS) -> None:
        pcm_bytes, sr, ch = read_wav(str(wav_path))
        if sr != AUDIO_SAMPLE_RATE or ch != 1:
            raise ValueError(f"Expected {AUDIO_SAMPLE_RATE} Hz mono WAV, got {sr} Hz / {ch} ch")
        self._samples = np.frombuffer(pcm_bytes, dtype=np.int16)
        self._block_samples = int(sr * block_ms / 1000)
        self._block_period = block_ms / 1000.0
        self._total_blocks = len(self._samples) // self._block_samples

        self._is_capturing = False
        self._lock = threading.Lock()
        self._next_index = 0
        self._loops_done = 0
        self._start_mono: float | None = None
        self._pace_lag_max = 0.0

    @property
    def overflow_count(self) -> int:
        return 0  # No queue: frames are generated on demand, nothing to overflow

    @property
    def loops_done(self) -> int:
        with self._lock:
            return self._loops_done

    @property
    def pace_lag_max(self) -> float:
        with self._lock:
            return self._pace_lag_max

    def is_active(self) -> bool:
        return self._is_capturing

    def start(self) -> None:
        with self._lock:
            self._is_capturing = True
            self._start_mono = time.monotonic()
            self._next_index = 0

    def stop(self) -> None:
        with self._lock:
            self._is_capturing = False

    def close(self) -> None:
        self.stop()

    def drain(self):
        return []

    def get_frame(self, timeout: float | None = None) -> AudioFrame | None:
        with self._lock:
            if not self._is_capturing or self._start_mono is None:
                return None
            index = self._next_index
            due = self._start_mono + index * self._block_period
            self._next_index += 1
            if self._next_index >= self._total_blocks:
                self._next_index = 0
                self._start_mono += self._total_blocks * self._block_period
                self._loops_done += 1

        now = time.monotonic()
        lag = now - due
        if lag < 0:
            time.sleep(-lag)  # Frame due in the future: wait for the audio timeline
        with self._lock:
            if lag > self._pace_lag_max:
                self._pace_lag_max = lag  # Behind schedule: deliver immediately, record lag

        lo = index * self._block_samples
        chunk = self._samples[lo : lo + self._block_samples]
        return AudioFrame(
            data=chunk.tobytes(),
            sample_rate=AUDIO_SAMPLE_RATE,
            channels=1,
            timestamp_ns=time.monotonic_ns(),
            samples_count=len(chunk),
        )


# --- Soak orchestration --------------------------------------------------------

class SoakTest:
    def __init__(self, duration_minutes: float, headless: bool) -> None:
        self.duration_s = duration_minutes * 60.0
        self.headless = headless

        self.source = ScriptedSpeechSource(CONTINUOUS_WAV)
        self.event_queue = CountingQueue()
        self.controller = ListeningController(
            engine=None,  # Default VoskEngine (production configuration)
            audio_source_factory=lambda: self.source,
            event_queue=self.event_queue,  # type: ignore[arg-type]
        )

        self.exceptions: list[str] = []
        self.samples: list[dict] = []
        self.max_queue_depth = 0
        self.max_gui_stall_s = 0.0
        self.stall_events: list[dict] = []  # Every GUI stall > 100 ms (AC-7)
        self._soak_start = time.monotonic()
        self.adds = 0
        self.discards = 0
        self.undos = 0
        self._stop_monitor = threading.Event()
        self._last_cpu = time.process_time()
        self._last_wall = time.monotonic()
        self.app = None  # VoiceCalculatorApp when GUI mode

    # -- Monitor thread ---------------------------------------------------------

    def _sample_once(self, elapsed: float) -> None:
        cpu_now = time.process_time()
        wall_now = time.monotonic()
        cpu_percent = 100.0 * (cpu_now - self._last_cpu) / max(wall_now - self._last_wall, 1e-6)
        self._last_cpu, self._last_wall = cpu_now, wall_now

        depth = self.event_queue.qsize()
        self.max_queue_depth = max(self.max_queue_depth, depth)
        rss = get_rss_mb()
        sample = {
            "elapsed_s": round(elapsed, 1),
            "rss_mb": round(rss, 1) if rss is not None else "",
            "cpu_percent": round(cpu_percent, 2),
            "queue_depth": depth,
            "gui_stall_ms": round(self.max_gui_stall_s * 1000.0, 1),
            "events_total": sum(self.event_queue.counts.values()),
            "decisions": self.event_queue.counts[ControllerEventType.DECISION.name],
            "errors": self.event_queue.counts[ControllerEventType.ERROR.name],
            "adds": self.adds,
            "discards": self.discards,
            "undos": self.undos,
            "loops": self.source.loops_done,
            "pace_lag_ms": round(self.source.pace_lag_max * 1000.0, 1),
        }
        self.samples.append(sample)

    def _monitor_loop(self) -> None:
        start = time.monotonic()
        while not self._stop_monitor.wait(timeout=5.0):
            self._sample_once(time.monotonic() - start)

    # -- GUI auto-responder + stall probe (main thread via after()) -------------

    def _install_gui_instrumentation(self) -> None:
        app = self.app
        assert app is not None
        root = app.root

        # Capture Tk callback exceptions instead of letting them print silently
        def report_callback_exception(exc_type, exc_value, tb):
            self.exceptions.append(f"TkCallback: {exc_type.__name__}: {exc_value}")

        root.report_callback_exception = report_callback_exception

        # AC-7 probe: a 100 ms after() chain; lateness = GUI event-loop stall
        state = {"due": time.monotonic() + 0.1}

        def stall_probe():
            now = time.monotonic()
            lateness = now - state["due"]
            if lateness > self.max_gui_stall_s:
                self.max_gui_stall_s = lateness
            if lateness > 0.1:  # AC-7 threshold: log every stall over 100 ms
                self.stall_events.append(
                    {"elapsed_s": round(now - self._soak_start, 1), "stall_ms": round(lateness * 1000.0, 1)}
                )
            # Resync if we missed multiple periods (one big stall already recorded)
            state["due"] = max(state["due"] + 0.1, now + 0.1)
            if not self._stop_monitor.is_set():
                root.after(100, stall_probe)

        root.after(100, stall_probe)

        # Auto-responder: resolve pending candidates like a user would
        responder_state = {"candidate": None, "first_seen": 0.0, "decisions_seen": 0}

        def respond():
            try:
                pending = self.app.pending_candidate
                if pending is not None:
                    if responder_state["candidate"] is not pending:
                        responder_state["candidate"] = pending
                        responder_state["first_seen"] = time.monotonic()
                        responder_state["decisions_seen"] += 1
                    elif time.monotonic() - responder_state["first_seen"] >= 1.5:
                        # Deterministic mix: every 4th candidate discarded, rest added
                        if responder_state["decisions_seen"] % 4 == 0:
                            self.app.on_confirm_discard()
                            self.discards += 1
                        else:
                            self.app.on_confirm_add()
                            self.adds += 1
                            if self.adds % 40 == 0:
                                self.app.on_undo()
                                self.undos += 1
                        responder_state["candidate"] = None
            except Exception as e:  # Never kill the soak loop
                self.exceptions.append(f"Responder: {type(e).__name__}: {e}")
            if not self._stop_monitor.is_set():
                root.after(200, respond)

        root.after(200, respond)

    def _finish(self) -> None:
        self._stop_monitor.set()
        if self.app is not None:
            try:
                self.app.on_stop()
            except Exception as e:
                self.exceptions.append(f"Finish on_stop: {type(e).__name__}: {e}")
            try:
                self.app.root.quit()  # Exit mainloop; destroy happens after
            except Exception as e:
                self.exceptions.append(f"Finish quit: {type(e).__name__}: {e}")
        else:
            # Headless: stop the controller directly
            self.controller.stop(timeout=2.0)

    # -- Entry point --------------------------------------------------------------

    def run(self) -> dict:
        start_wall = time.monotonic()
        monitor = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor.start()

        if self.headless:
            self.controller.start()
            time.sleep(self.duration_s)
            self._finish()
        else:
            import tkinter as tk

            from voice_calculator.gui.app import VoiceCalculatorApp

            root = tk.Tk()
            self.app = VoiceCalculatorApp(root=root, controller=self.controller)
            self._install_gui_instrumentation()
            root.after(1000, self.app.on_start)  # Begin listening (no user to press Start)
            root.after(int(self.duration_s * 1000), self._finish)
            root.mainloop()
            try:
                root.destroy()
            except Exception:
                pass

        self._stop_monitor.set()
        self._sample_once(time.monotonic() - start_wall)
        monitor.join(timeout=2.0)

        return self.build_summary(elapsed=time.monotonic() - start_wall)

    # -- Reporting -----------------------------------------------------------------

    def _nearest_sample(self, target_s: float) -> dict | None:
        if not self.samples:
            return None
        return min(self.samples, key=lambda s: abs(s["elapsed_s"] - target_s))

    def build_summary(self, elapsed: float) -> dict:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10,
            ).stdout.strip()
        except Exception:
            commit = "unknown"

        warmup = self._nearest_sample(300.0) or self._nearest_sample(min(300.0, elapsed / 2))
        at_30 = self._nearest_sample(1800.0)
        at_60 = self._nearest_sample(elapsed)

        def rss_of(sample: dict | None) -> float | None:
            if sample and sample["rss_mb"] != "":
                return float(sample["rss_mb"])
            return None

        rss_start = rss_of(self._nearest_sample(0.0))
        rss_warmup = rss_of(warmup)
        rss_end = rss_of(at_60)
        rss_growth = (
            round(rss_end - rss_warmup, 1)
            if rss_warmup is not None and rss_end is not None
            else None
        )

        decisions = self.event_queue.counts[ControllerEventType.DECISION.name]
        expected_utts = int(self.source.loops_done * 19)  # EXP-006: ~19 utterances per 106s loop @ 500/700

        return {
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_s": round(elapsed, 1),
            "commit": commit,
            "mode": "headless" if self.headless else "gui",
            "crashes": self.exceptions,
            "max_queue_depth": self.max_queue_depth,
            "rss_start_mb": rss_start,
            "rss_30min_mb": rss_of(at_30),
            "rss_end_mb": rss_end,
            "rss_growth_mb_since_warmup": rss_growth,
            "cpu_percent_avg": round(
                sum(s["cpu_percent"] for s in self.samples) / max(len(self.samples), 1), 2
            ),
            "cpu_percent_max": round(max((s["cpu_percent"] for s in self.samples), default=0.0), 2),
            "max_gui_stall_ms": round(self.max_gui_stall_s * 1000.0, 1) if not self.headless else None,
            "stalls_over_100ms": self.stall_events if not self.headless else None,
            "event_counts": dict(self.event_queue.counts),
            "error_events": self.event_queue.counts[ControllerEventType.ERROR.name],
            "adds": self.adds,
            "discards": self.discards,
            "undos": self.undos,
            "loops_completed": self.source.loops_done,
            "expected_utterances": expected_utts,
            "decisions_processed": decisions,
            "missed_utterances": max(expected_utts - decisions, 0),
            "pace_lag_max_ms": round(self.source.pace_lag_max * 1000.0, 1),
            "samples": len(self.samples),
        }


def write_outputs(soak: SoakTest, summary: dict) -> None:
    SAMPLES_CSV.parent.mkdir(exist_ok=True)
    if soak.samples:
        with open(SAMPLES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(soak.samples[0].keys()))
            writer.writeheader()
            writer.writerows(soak.samples)
    with open(SUMMARY_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Voice Calculator long-session soak test")
    parser.add_argument("--duration-minutes", type=float, default=60.0)
    parser.add_argument("--headless", action="store_true", help="Run without the Tkinter GUI")
    args = parser.parse_args()

    if not CONTINUOUS_WAV.exists():
        print(f"ERROR: scripted speech WAV not found: {CONTINUOUS_WAV}")
        sys.exit(1)

    print(f"Soak test: {args.duration_minutes:.0f} min, mode={'headless' if args.headless else 'gui'}")
    print(f"Scripted source: {CONTINUOUS_WAV.name} (looped in real time, no microphone)")
    print(f"Output: {SUMMARY_JSON.name} + {SAMPLES_CSV.name} in analysis/")
    if not args.headless:
        print("A Voice Calculator window will open and close itself when the run completes.")

    soak = SoakTest(duration_minutes=args.duration_minutes, headless=args.headless)
    try:
        summary = soak.run()
    except Exception as e:
        soak.exceptions.append(f"Fatal: {type(e).__name__}: {e}")
        summary = soak.build_summary(elapsed=0.0)

    write_outputs(soak, summary)

    print("\n# Soak Test Summary")
    for key, value in summary.items():
        if key != "crashes":
            print(f"- {key}: {value}")
    print(f"- crashes: {summary['crashes'] or 'none'}")

    if soak.exceptions:
        sys.exit(1)


if __name__ == "__main__":
    main()
