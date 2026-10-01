"""Benchmark and evaluation pipeline for offline ASR models.

Provides:
- Dataset sample representation and CSV label parser.
- Deterministic sample outcome classification (CORRECT_ACCEPT, FALSE_ADDITION, etc.).
- Complete metrics computation per docs/research.md §4:
  * Exact Integer Accuracy (EIA)
  * False Addition Rate (primary safety metric)
  * False Acceptance Rate (on negative utterances)
  * Rejection Rate & False Rejection Rate
  * Rule-of-three 95% upper bound for zero-error observations
  * Latency distributions (p50, p95, min, max, mean)
  * Multi-dimensional breakdowns by category, speaker, and split.
- Human-readable reporting and CSV export.
"""

import csv
from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from voice_calculator.asr.base import ASREngine, ASRResult, ASRStatus
from voice_calculator.audio.wavio import WavFormatError, read_wav
from voice_calculator.numparse import ParseResult, ParseStatus, RejectReason, parse


class SampleOutcome(Enum):
    """Classification of an individual evaluation sample outcome."""

    CORRECT_ACCEPT = "CORRECT_ACCEPT"  # Valid utterance parsed to exact ground-truth integer
    FALSE_ADDITION = "FALSE_ADDITION"  # Wrong integer on valid input, or any integer on negative input
    CORRECT_REJECT = "CORRECT_REJECT"  # Negative utterance properly rejected (or no speech)
    FALSE_REJECT = "FALSE_REJECT"      # Valid utterance improperly rejected (or no speech)
    ERROR = "ERROR"                    # File missing, malformed WAV, or engine exception


@dataclass(frozen=True)
class SampleLabel:
    """Ground truth label for an evaluation audio file."""

    file: str
    expected_value: Optional[int]  # None indicates NEGATIVE (non-number, out-of-range, noise, silence)
    category: str = "canonical"
    speaker: str = "unknown"
    session_id: str = "1"
    split: str = "dev"
    notes: str = ""

    @property
    def is_negative(self) -> bool:
        """True if the sample is in the negative class (expected_value is None)."""
        return self.expected_value is None


@dataclass(frozen=True)
class SampleResult:
    """Result of running ASR and parsing on a single evaluation sample."""

    sample: SampleLabel
    outcome: SampleOutcome
    asr_text: str = ""
    parsed_value: Optional[int] = None
    parse_status: Optional[str] = None
    reject_reason: Optional[str] = None
    asr_status: str = ASRStatus.SUCCESS.value
    elapsed_ms: float = 0.0
    error_message: Optional[str] = None


@dataclass(frozen=True)
class BenchmarkMetrics:
    """Summary metrics calculated from evaluation results per docs/research.md §4."""

    total_samples: int = 0
    valid_samples: int = 0
    negative_samples: int = 0
    error_samples: int = 0

    correct_accept_count: int = 0
    false_addition_count: int = 0
    false_addition_valid_count: int = 0
    false_addition_neg_count: int = 0
    correct_reject_count: int = 0
    false_reject_count: int = 0

    exact_integer_accuracy: float = 0.0
    false_addition_rate: float = 0.0
    false_acceptance_rate: float = 0.0
    false_rejection_rate: float = 0.0
    rejection_rate: float = 0.0
    rule_of_three_upper_bound: Optional[float] = None

    latency_min_ms: float = 0.0
    latency_mean_ms: float = 0.0
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    latency_max_ms: float = 0.0

    category_metrics: Dict[str, "BenchmarkMetrics"] = field(default_factory=dict)
    speaker_metrics: Dict[str, "BenchmarkMetrics"] = field(default_factory=dict)
    split_metrics: Dict[str, "BenchmarkMetrics"] = field(default_factory=dict)


def parse_expected_value(raw: str) -> Optional[int]:
    """Parses ground-truth integer or NEGATIVE designation from raw string.

    Args:
        raw: Raw value string from CSV (e.g. '42', 'NEGATIVE', 'negative', '').

    Returns:
        Integer value if valid integer string, or None if NEGATIVE/empty.

    Raises:
        ValueError: If raw is not a valid integer and not recognized as NEGATIVE.
    """
    cleaned = raw.strip()
    if not cleaned or cleaned.upper() == "NEGATIVE":
        return None
    try:
        return int(cleaned)
    except ValueError as e:
        raise ValueError(
            f"Invalid expected_value '{raw}'. Expected an integer (0-2000) or 'NEGATIVE'."
        ) from e


def load_labels_csv(csv_path: Union[str, Path]) -> List[SampleLabel]:
    """Loads and validates dataset labels from a CSV file.

    Expected CSV columns:
        file, expected_value_or_NEGATIVE, category, speaker, session_id, split, notes

    Args:
        csv_path: Path to the labels CSV file.

    Returns:
        List of parsed SampleLabel instances.

    Raises:
        FileNotFoundError: If csv_path does not exist.
        ValueError: If CSV headers or row contents are invalid.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"Labels CSV file not found: {path}")

    labels: List[SampleLabel] = []

    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"Labels CSV file is empty: {path}")

        # Normalize column header lookup (case-insensitive and trimmed)
        header_map = {name.strip().lower(): name for name in reader.fieldnames if name}

        file_col = header_map.get("file")
        if not file_col:
            raise ValueError(f"Missing required 'file' column in CSV: {path}")

        # Support 'expected_value_or_negative', 'expected_value', or 'value'
        val_col = (
            header_map.get("expected_value_or_negative")
            or header_map.get("expected_value")
            or header_map.get("value")
        )
        if not val_col:
            raise ValueError(
                f"Missing required 'expected_value_or_NEGATIVE' column in CSV: {path}"
            )

        cat_col = header_map.get("category")
        speaker_col = header_map.get("speaker")
        session_col = header_map.get("session_id")
        split_col = header_map.get("split")
        notes_col = header_map.get("notes")

        for row_idx, row in enumerate(reader, start=2):
            filename = (row.get(file_col) or "").strip()
            if not filename or filename.startswith("#"):
                continue  # Skip blank lines or comments

            raw_val = (row.get(val_col) or "").strip()
            try:
                expected_val = parse_expected_value(raw_val)
            except ValueError as e:
                raise ValueError(f"Row {row_idx}: {e}") from e

            category = (row.get(cat_col) or "canonical").strip() if cat_col else "canonical"
            speaker = (row.get(speaker_col) or "unknown").strip() if speaker_col else "unknown"
            session_id = (row.get(session_col) or "1").strip() if session_col else "1"
            split = (row.get(split_col) or "dev").strip() if split_col else "dev"
            notes = (row.get(notes_col) or "").strip() if notes_col else ""

            labels.append(
                SampleLabel(
                    file=filename,
                    expected_value=expected_val,
                    category=category or "canonical",
                    speaker=speaker or "unknown",
                    session_id=session_id or "1",
                    split=split or "dev",
                    notes=notes,
                )
            )

    return labels


def evaluate_sample(
    engine: ASREngine,
    pcm_bytes: bytes,
    expected_value: Optional[int],
) -> Tuple[SampleOutcome, ASRResult, ParseResult]:
    """Transcribes audio with ASREngine, parses transcript with numparse, and classifies outcome.

    Args:
        engine: Loaded ASREngine instance.
        pcm_bytes: Raw 16-bit mono 16 kHz PCM audio bytes.
        expected_value: Target integer or None (for NEGATIVE samples).

    Returns:
        Tuple of (SampleOutcome, ASRResult, ParseResult).
    """
    asr_res = engine.transcribe(pcm_bytes)

    if asr_res.status == ASRStatus.ERROR:
        parse_res = ParseResult(
            status=ParseStatus.REJECTED,
            reason=RejectReason.UNSUPPORTED,
            normalized_text="",
        )
        return SampleOutcome.ERROR, asr_res, parse_res

    # Normal transcription or NO_SPEECH
    parse_res = parse(asr_res.text)

    if expected_value is not None:
        # Valid utterance expected
        if parse_res.status == ParseStatus.SUCCESS:
            if parse_res.value == expected_value:
                outcome = SampleOutcome.CORRECT_ACCEPT
            else:
                outcome = SampleOutcome.FALSE_ADDITION
        else:
            outcome = SampleOutcome.FALSE_REJECT
    else:
        # Negative utterance expected
        if parse_res.status == ParseStatus.SUCCESS:
            outcome = SampleOutcome.FALSE_ADDITION
        else:
            outcome = SampleOutcome.CORRECT_REJECT

    return outcome, asr_res, parse_res


def _calculate_percentile(sorted_values: Sequence[float], percentile: float) -> float:
    """Calculates percentile from sorted float sequence (0.0 - 1.0)."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = percentile * (len(sorted_values) - 1)
    lower = int(math.floor(index))
    upper = int(math.ceil(index))
    if lower == upper:
        return sorted_values[lower]
    weight = index - lower
    return (1.0 - weight) * sorted_values[lower] + weight * sorted_values[upper]


def compute_metrics(results: Sequence[SampleResult]) -> BenchmarkMetrics:
    """Calculates evaluation metrics and breakdowns across a list of SampleResult items.

    Args:
        results: Collection of evaluated sample results.

    Returns:
        BenchmarkMetrics containing aggregate counts, rates, latency stats, and breakdowns.
    """
    if not results:
        return BenchmarkMetrics()

    total_samples = len(results)
    valid_samples = 0
    negative_samples = 0
    error_samples = 0

    correct_accept_count = 0
    false_addition_count = 0
    false_addition_valid_count = 0
    false_addition_neg_count = 0
    correct_reject_count = 0
    false_reject_count = 0

    latencies: List[float] = []

    # Category, Speaker, Split groups
    category_groups: Dict[str, List[SampleResult]] = {}
    speaker_groups: Dict[str, List[SampleResult]] = {}
    split_groups: Dict[str, List[SampleResult]] = {}

    for res in results:
        cat = res.sample.category
        speaker = res.sample.speaker
        split = res.sample.split

        category_groups.setdefault(cat, []).append(res)
        speaker_groups.setdefault(speaker, []).append(res)
        split_groups.setdefault(split, []).append(res)

        if res.outcome == SampleOutcome.ERROR:
            error_samples += 1
            continue

        if res.sample.is_negative:
            negative_samples += 1
        else:
            valid_samples += 1

        if res.elapsed_ms > 0:
            latencies.append(res.elapsed_ms)

        if res.outcome == SampleOutcome.CORRECT_ACCEPT:
            correct_accept_count += 1
        elif res.outcome == SampleOutcome.FALSE_ADDITION:
            false_addition_count += 1
            if res.sample.is_negative:
                false_addition_neg_count += 1
            else:
                false_addition_valid_count += 1
        elif res.outcome == SampleOutcome.CORRECT_REJECT:
            correct_reject_count += 1
        elif res.outcome == SampleOutcome.FALSE_REJECT:
            false_reject_count += 1

    evaluated_count = valid_samples + negative_samples

    # Metrics formulas (research.md §4)
    exact_integer_accuracy = (
        (correct_accept_count / valid_samples) if valid_samples > 0 else 0.0
    )
    false_addition_rate = (
        (false_addition_count / evaluated_count) if evaluated_count > 0 else 0.0
    )
    false_acceptance_rate = (
        (false_addition_neg_count / negative_samples) if negative_samples > 0 else 0.0
    )
    false_rejection_rate = (
        (false_reject_count / valid_samples) if valid_samples > 0 else 0.0
    )
    rejection_rate = (
        ((correct_reject_count + false_reject_count) / evaluated_count)
        if evaluated_count > 0
        else 0.0
    )

    # Rule of three upper bound for zero false additions
    rule_of_three: Optional[float] = None
    if evaluated_count > 0 and false_addition_count == 0:
        rule_of_three = 3.0 / evaluated_count

    # Latency statistics
    lat_min = 0.0
    lat_mean = 0.0
    lat_p50 = 0.0
    lat_p95 = 0.0
    lat_max = 0.0

    if latencies:
        latencies.sort()
        lat_min = latencies[0]
        lat_max = latencies[-1]
        lat_mean = sum(latencies) / len(latencies)
        lat_p50 = _calculate_percentile(latencies, 0.50)
        lat_p95 = _calculate_percentile(latencies, 0.95)

    # Recursive metric breakdowns (without nested breakdowns to avoid infinite recursion)
    def _compute_leaf_metrics(group_results: List[SampleResult]) -> BenchmarkMetrics:
        v_count = sum(1 for r in group_results if not r.sample.is_negative and r.outcome != SampleOutcome.ERROR)
        n_count = sum(1 for r in group_results if r.sample.is_negative and r.outcome != SampleOutcome.ERROR)
        err_count = sum(1 for r in group_results if r.outcome == SampleOutcome.ERROR)
        c_acc = sum(1 for r in group_results if r.outcome == SampleOutcome.CORRECT_ACCEPT)
        f_add = sum(1 for r in group_results if r.outcome == SampleOutcome.FALSE_ADDITION)
        f_add_v = sum(1 for r in group_results if r.outcome == SampleOutcome.FALSE_ADDITION and not r.sample.is_negative)
        f_add_n = sum(1 for r in group_results if r.outcome == SampleOutcome.FALSE_ADDITION and r.sample.is_negative)
        c_rej = sum(1 for r in group_results if r.outcome == SampleOutcome.CORRECT_REJECT)
        f_rej = sum(1 for r in group_results if r.outcome == SampleOutcome.FALSE_REJECT)

        eval_cnt = v_count + n_count
        eia = (c_acc / v_count) if v_count > 0 else 0.0
        far = (f_add / eval_cnt) if eval_cnt > 0 else 0.0
        fa_neg = (f_add_n / n_count) if n_count > 0 else 0.0
        frr = (f_rej / v_count) if v_count > 0 else 0.0
        rej_r = ((c_rej + f_rej) / eval_cnt) if eval_cnt > 0 else 0.0
        r3 = (3.0 / eval_cnt) if eval_cnt > 0 and f_add == 0 else None

        lats = [r.elapsed_ms for r in group_results if r.elapsed_ms > 0 and r.outcome != SampleOutcome.ERROR]
        lats.sort()
        l_min = lats[0] if lats else 0.0
        l_max = lats[-1] if lats else 0.0
        l_mean = (sum(lats) / len(lats)) if lats else 0.0
        l_50 = _calculate_percentile(lats, 0.50) if lats else 0.0
        l_95 = _calculate_percentile(lats, 0.95) if lats else 0.0

        return BenchmarkMetrics(
            total_samples=len(group_results),
            valid_samples=v_count,
            negative_samples=n_count,
            error_samples=err_count,
            correct_accept_count=c_acc,
            false_addition_count=f_add,
            false_addition_valid_count=f_add_v,
            false_addition_neg_count=f_add_n,
            correct_reject_count=c_rej,
            false_reject_count=f_rej,
            exact_integer_accuracy=eia,
            false_addition_rate=far,
            false_acceptance_rate=fa_neg,
            false_rejection_rate=frr,
            rejection_rate=rej_r,
            rule_of_three_upper_bound=r3,
            latency_min_ms=l_min,
            latency_mean_ms=l_mean,
            latency_p50_ms=l_50,
            latency_p95_ms=l_95,
            latency_max_ms=l_max,
        )

    cat_metrics = {k: _compute_leaf_metrics(v) for k, v in category_groups.items()}
    spk_metrics = {k: _compute_leaf_metrics(v) for k, v in speaker_groups.items()}
    splt_metrics = {k: _compute_leaf_metrics(v) for k, v in split_groups.items()}

    return BenchmarkMetrics(
        total_samples=total_samples,
        valid_samples=valid_samples,
        negative_samples=negative_samples,
        error_samples=error_samples,
        correct_accept_count=correct_accept_count,
        false_addition_count=false_addition_count,
        false_addition_valid_count=false_addition_valid_count,
        false_addition_neg_count=false_addition_neg_count,
        correct_reject_count=correct_reject_count,
        false_reject_count=false_reject_count,
        exact_integer_accuracy=exact_integer_accuracy,
        false_addition_rate=false_addition_rate,
        false_acceptance_rate=false_acceptance_rate,
        false_rejection_rate=false_rejection_rate,
        rejection_rate=rejection_rate,
        rule_of_three_upper_bound=rule_of_three,
        latency_min_ms=lat_min,
        latency_mean_ms=lat_mean,
        latency_p50_ms=lat_p50,
        latency_p95_ms=lat_p95,
        latency_max_ms=lat_max,
        category_metrics=cat_metrics,
        speaker_metrics=spk_metrics,
        split_metrics=splt_metrics,
    )


def run_benchmark(
    engine: ASREngine,
    dataset_dir: Union[str, Path],
    labels: Sequence[SampleLabel],
) -> Tuple[List[SampleResult], BenchmarkMetrics]:
    """Runs ASR benchmark evaluation over a list of labeled audio samples.

    Args:
        engine: ASREngine instance (must be loaded or capable of loading).
        dataset_dir: Directory containing audio files.
        labels: Sequence of SampleLabel instances to evaluate.

    Returns:
        Tuple of (List[SampleResult], BenchmarkMetrics).
    """
    if not engine.is_loaded:
        engine.load()

    base_dir = Path(dataset_dir)
    results: List[SampleResult] = []

    for label in labels:
        audio_path = base_dir / label.file
        if not audio_path.is_file():
            # Missing file error
            results.append(
                SampleResult(
                    sample=label,
                    outcome=SampleOutcome.ERROR,
                    error_message=f"Audio file not found: {audio_path}",
                )
            )
            continue

        try:
            pcm_bytes, sample_rate, channels = read_wav(audio_path)
        except (WavFormatError, FileNotFoundError, Exception) as e:
            results.append(
                SampleResult(
                    sample=label,
                    outcome=SampleOutcome.ERROR,
                    error_message=f"Failed to read WAV {audio_path.name}: {e}",
                )
            )
            continue

        try:
            outcome, asr_res, parse_res = evaluate_sample(
                engine=engine,
                pcm_bytes=pcm_bytes,
                expected_value=label.expected_value,
            )

            results.append(
                SampleResult(
                    sample=label,
                    outcome=outcome,
                    asr_text=asr_res.text,
                    parsed_value=parse_res.value,
                    parse_status=parse_res.status.value if parse_res else None,
                    reject_reason=parse_res.reason.value if (parse_res and parse_res.reason) else None,
                    asr_status=asr_res.status.value,
                    elapsed_ms=asr_res.elapsed_ms,
                    error_message=asr_res.error_message,
                )
            )
        except Exception as e:
            results.append(
                SampleResult(
                    sample=label,
                    outcome=SampleOutcome.ERROR,
                    error_message=f"Evaluation exception on {label.file}: {e}",
                )
            )

    metrics = compute_metrics(results)
    return results, metrics


def format_benchmark_report(
    metrics: BenchmarkMetrics,
    engine_name: str,
    split_filter: Optional[str] = None,
) -> str:
    """Formats a human-readable benchmark evaluation summary report."""
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append(f"VOICE CALCULATOR ASR BENCHMARK REPORT — Engine: {engine_name}")
    if split_filter:
        lines.append(f"Filter: Split = '{split_filter}'")
    lines.append("=" * 78)

    lines.append("\n1. SAMPLE SUMMARY")
    lines.append(f"  Total samples processed:   {metrics.total_samples}")
    lines.append(f"  Valid number utterances:   {metrics.valid_samples}")
    lines.append(f"  Negative class utterances: {metrics.negative_samples}")
    lines.append(f"  Unreadable/Error samples:  {metrics.error_samples}")

    lines.append("\n2. PRIMARY SAFETY & ACCURACY METRICS (per docs/research.md §4)")
    eia_pct = metrics.exact_integer_accuracy * 100.0
    lines.append(
        f"  Exact Integer Accuracy (EIA):       {eia_pct:6.2f}% ({metrics.correct_accept_count}/{metrics.valid_samples})"
    )

    far_pct = metrics.false_addition_rate * 100.0
    evaluated = metrics.valid_samples + metrics.negative_samples
    lines.append(
        f"  False Addition Rate (ALL):          {far_pct:6.2f}% ({metrics.false_addition_count}/{evaluated}) [PRIMARY SAFETY]"
    )
    lines.append(
        f"    - On valid utterances (wrong val): {metrics.false_addition_valid_count}/{metrics.valid_samples}"
    )
    lines.append(
        f"    - On negative utterances (halluc): {metrics.false_addition_neg_count}/{metrics.negative_samples}"
    )

    if metrics.rule_of_three_upper_bound is not None:
        ub_pct = metrics.rule_of_three_upper_bound * 100.0
        lines.append(
            f"  95% False Addition Upper Bound:     ~{ub_pct:6.2f}% (Rule of three for 0 errors in {evaluated} trials)"
        )

    fa_neg_pct = metrics.false_acceptance_rate * 100.0
    lines.append(
        f"  False Acceptance Rate (Negatives):  {fa_neg_pct:6.2f}% ({metrics.false_addition_neg_count}/{metrics.negative_samples})"
    )

    frr_pct = metrics.false_rejection_rate * 100.0
    lines.append(
        f"  False Rejection Rate (Valid utts):  {frr_pct:6.2f}% ({metrics.false_reject_count}/{metrics.valid_samples})"
    )

    rej_pct = metrics.rejection_rate * 100.0
    total_rej = metrics.correct_reject_count + metrics.false_reject_count
    lines.append(
        f"  Total Rejection Rate:               {rej_pct:6.2f}% ({total_rej}/{evaluated})"
    )

    lines.append("\n3. LATENCY DISTRIBUTION (Inference ms)")
    lines.append(
        f"  p50: {metrics.latency_p50_ms:6.1f} ms | p95: {metrics.latency_p95_ms:6.1f} ms | mean: {metrics.latency_mean_ms:6.1f} ms | min: {metrics.latency_min_ms:6.1f} ms | max: {metrics.latency_max_ms:6.1f} ms"
    )

    if metrics.category_metrics:
        lines.append("\n4. BREAKDOWN BY CATEGORY")
        lines.append(
            f"  {'Category':<24} {'N':>5} {'EIA %':>8} {'FalseAdd':>10} {'Reject %':>10} {'p50 ms':>8}"
        )
        lines.append("  " + "-" * 68)
        for cat, cm in sorted(metrics.category_metrics.items()):
            c_eia = f"{cm.exact_integer_accuracy * 100.0:5.1f}%" if cm.valid_samples > 0 else "n/a"
            c_rej = f"{cm.rejection_rate * 100.0:5.1f}%"
            lines.append(
                f"  {cat:<24} {cm.total_samples:>5} {c_eia:>8} {cm.false_addition_count:>10} {c_rej:>10} {cm.latency_p50_ms:>8.1f}"
            )

    if metrics.speaker_metrics and len(metrics.speaker_metrics) > 1:
        lines.append("\n5. BREAKDOWN BY SPEAKER")
        lines.append(
            f"  {'Speaker':<20} {'N':>5} {'EIA %':>8} {'FalseAdd':>10} {'p50 ms':>8}"
        )
        lines.append("  " + "-" * 56)
        for spk, sm in sorted(metrics.speaker_metrics.items()):
            s_eia = f"{sm.exact_integer_accuracy * 100.0:5.1f}%" if sm.valid_samples > 0 else "n/a"
            lines.append(
                f"  {spk:<20} {sm.total_samples:>5} {s_eia:>8} {sm.false_addition_count:>10} {sm.latency_p50_ms:>8.1f}"
            )

    lines.append("\n" + "=" * 78)
    return "\n".join(lines)


def export_results_csv(
    results: Sequence[SampleResult],
    out_csv_path: Union[str, Path],
) -> None:
    """Exports per-utterance benchmark results to a CSV file.

    Args:
        results: Sequence of SampleResult objects.
        out_csv_path: Target CSV file path.
    """
    path = Path(out_csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "file",
                "expected_value",
                "is_negative",
                "category",
                "speaker",
                "session_id",
                "split",
                "outcome",
                "asr_status",
                "asr_text",
                "parsed_value",
                "parse_status",
                "reject_reason",
                "elapsed_ms",
                "error_message",
            ]
        )
        for r in results:
            writer.writerow(
                [
                    r.sample.file,
                    r.sample.expected_value if r.sample.expected_value is not None else "NEGATIVE",
                    1 if r.sample.is_negative else 0,
                    r.sample.category,
                    r.sample.speaker,
                    r.sample.session_id,
                    r.sample.split,
                    r.outcome.value,
                    r.asr_status,
                    r.asr_text,
                    r.parsed_value if r.parsed_value is not None else "",
                    r.parse_status or "",
                    r.reject_reason or "",
                    f"{r.elapsed_ms:.2f}",
                    r.error_message or "",
                ]
            )
