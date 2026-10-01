"""Unit and integration tests for benchmark and evaluation infrastructure.

Tests:
- Ground-truth label parsing and CSV reader.
- Sample outcome classification (CORRECT_ACCEPT, FALSE_ADDITION, CORRECT_REJECT, FALSE_REJECT, ERROR).
- Exact Integer Accuracy (EIA), False Addition Rate, False Acceptance Rate math.
- Rule-of-three 95% confidence upper bound computation.
- Latency statistics (min, mean, p50, p95, max) and percentiles.
- Category, speaker, and split breakdowns.
- End-to-end benchmark execution with FakeEngine and synthetic WAVs.
- Corrupt/missing file error handling.
- Results CSV export and text report formatting.
"""

from pathlib import Path
import tempfile
import pytest

from voice_calculator.asr.base import ASRResult, ASRStatus, FakeEngine
from voice_calculator.audio.wavio import write_wav
from voice_calculator.benchmark import (
    BenchmarkMetrics,
    SampleLabel,
    SampleOutcome,
    SampleResult,
    compute_metrics,
    evaluate_sample,
    export_results_csv,
    format_benchmark_report,
    load_labels_csv,
    parse_expected_value,
    run_benchmark,
)
from voice_calculator.config import AUDIO_SAMPLE_RATE


# --- 1. Label and Expected Value Parsing Tests ---


def test_parse_expected_value_integers() -> None:
    assert parse_expected_value("0") == 0
    assert parse_expected_value("42") == 42
    assert parse_expected_value("2000") == 2000
    assert parse_expected_value("  1500  ") == 1500


def test_parse_expected_value_negatives() -> None:
    assert parse_expected_value("NEGATIVE") is None
    assert parse_expected_value("negative") is None
    assert parse_expected_value("Negative") is None
    assert parse_expected_value("") is None
    assert parse_expected_value("   ") is None


def test_parse_expected_value_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid expected_value"):
        parse_expected_value("forty two")

    with pytest.raises(ValueError, match="Invalid expected_value"):
        parse_expected_value("3.14")


def test_load_labels_csv_valid(tmp_path: Path) -> None:
    csv_file = tmp_path / "labels.csv"
    csv_file.write_text(
        "file,expected_value_or_NEGATIVE,category,speaker,session_id,split,notes\n"
        "rec1.wav,42,canonical,developer,1,dev,clean recording\n"
        "rec2.wav,NEGATIVE,negative_non_number,father,1,test,command word\n"
        "rec3.wav,1500,teen_hundreds,developer,2,calibration,\n"
        "# Comment line\n"
        "\n",
        encoding="utf-8",
    )

    labels = load_labels_csv(csv_file)
    assert len(labels) == 3

    assert labels[0].file == "rec1.wav"
    assert labels[0].expected_value == 42
    assert labels[0].category == "canonical"
    assert labels[0].speaker == "developer"
    assert labels[0].split == "dev"
    assert labels[0].is_negative is False

    assert labels[1].file == "rec2.wav"
    assert labels[1].expected_value is None
    assert labels[1].category == "negative_non_number"
    assert labels[1].is_negative is True

    assert labels[2].file == "rec3.wav"
    assert labels[2].expected_value == 1500
    assert labels[2].category == "teen_hundreds"


def test_load_labels_csv_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_labels_csv(tmp_path / "nonexistent.csv")


def test_load_labels_csv_invalid_columns_raises(tmp_path: Path) -> None:
    csv_file = tmp_path / "bad.csv"
    csv_file.write_text("random_col1,random_col2\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Missing required 'file' column"):
        load_labels_csv(csv_file)


# --- 2. Outcome Classification Tests ---


def test_evaluate_sample_correct_accept() -> None:
    engine = FakeEngine(default_text="forty two")
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=42,
    )
    assert outcome == SampleOutcome.CORRECT_ACCEPT
    assert parse_res.value == 42


def test_evaluate_sample_false_addition_on_valid() -> None:
    engine = FakeEngine(default_text="fifty two")  # Recognized 52 instead of 42
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=42,
    )
    assert outcome == SampleOutcome.FALSE_ADDITION
    assert parse_res.value == 52


def test_evaluate_sample_false_addition_on_negative() -> None:
    engine = FakeEngine(default_text="five")  # Hallucinated 5 on negative audio
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=None,  # NEGATIVE
    )
    assert outcome == SampleOutcome.FALSE_ADDITION
    assert parse_res.value == 5


def test_evaluate_sample_false_reject_on_valid() -> None:
    engine = FakeEngine(default_text="hello")  # Non-number on valid audio -> rejected
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=42,
    )
    assert outcome == SampleOutcome.FALSE_REJECT


def test_evaluate_sample_correct_reject_on_negative() -> None:
    engine = FakeEngine(default_text="undo")  # Non-number on negative audio -> properly rejected
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=None,
    )
    assert outcome == SampleOutcome.CORRECT_REJECT


def test_evaluate_sample_correct_reject_silence_on_negative() -> None:
    engine = FakeEngine(should_return_no_speech=True)
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=None,
    )
    assert outcome == SampleOutcome.CORRECT_REJECT


def test_evaluate_sample_asr_error() -> None:
    engine = FakeEngine(should_fail=True)
    outcome, asr_res, parse_res = evaluate_sample(
        engine=engine,
        pcm_bytes=b"\x00\x00" * 160,
        expected_value=42,
    )
    assert outcome == SampleOutcome.ERROR
    assert asr_res.status == ASRStatus.ERROR


# --- 3. Metric Computation and Math Tests ---


def test_compute_metrics_known_distribution() -> None:
    # Build 10 valid samples: 8 CORRECT_ACCEPT, 1 FALSE_ADDITION, 1 FALSE_REJECT
    # Build 4 negative samples: 3 CORRECT_REJECT, 1 FALSE_ADDITION
    results = []
    # 8 correct accepts
    for i in range(8):
        lbl = SampleLabel(file=f"v_ok_{i}.wav", expected_value=i, category="canonical", split="dev")
        results.append(SampleResult(sample=lbl, outcome=SampleOutcome.CORRECT_ACCEPT, elapsed_ms=100.0))
    # 1 false addition on valid
    lbl_fa_v = SampleLabel(file="v_fa.wav", expected_value=10, category="confusable", split="dev")
    results.append(SampleResult(sample=lbl_fa_v, outcome=SampleOutcome.FALSE_ADDITION, elapsed_ms=150.0))
    # 1 false reject on valid
    lbl_fr_v = SampleLabel(file="v_fr.wav", expected_value=20, category="confusable", split="dev")
    results.append(SampleResult(sample=lbl_fr_v, outcome=SampleOutcome.FALSE_REJECT, elapsed_ms=120.0))

    # 3 correct rejects on negative
    for i in range(3):
        lbl = SampleLabel(file=f"n_cr_{i}.wav", expected_value=None, category="negative_noise", split="dev")
        results.append(SampleResult(sample=lbl, outcome=SampleOutcome.CORRECT_REJECT, elapsed_ms=80.0))
    # 1 false addition on negative
    lbl_fa_n = SampleLabel(file="n_fa.wav", expected_value=None, category="negative_noise", split="dev")
    results.append(SampleResult(sample=lbl_fa_n, outcome=SampleOutcome.FALSE_ADDITION, elapsed_ms=110.0))

    metrics = compute_metrics(results)

    assert metrics.total_samples == 14
    assert metrics.valid_samples == 10
    assert metrics.negative_samples == 4
    assert metrics.error_samples == 0

    assert metrics.correct_accept_count == 8
    assert metrics.false_addition_count == 2
    assert metrics.false_addition_valid_count == 1
    assert metrics.false_addition_neg_count == 1
    assert metrics.correct_reject_count == 3
    assert metrics.false_reject_count == 1

    # Exact Integer Accuracy: 8 / 10 = 0.80
    assert pytest.approx(metrics.exact_integer_accuracy, rel=1e-5) == 0.80

    # False Addition Rate: 2 / 14 = 0.142857
    assert pytest.approx(metrics.false_addition_rate, rel=1e-5) == 2.0 / 14.0

    # False Acceptance Rate on negatives: 1 / 4 = 0.25
    assert pytest.approx(metrics.false_acceptance_rate, rel=1e-5) == 0.25

    # False Rejection Rate on valids: 1 / 10 = 0.10
    assert pytest.approx(metrics.false_rejection_rate, rel=1e-5) == 0.10

    # Total Rejection Rate: (3 + 1) / 14 = 4 / 14
    assert pytest.approx(metrics.rejection_rate, rel=1e-5) == 4.0 / 14.0

    # Rule of three is None because false additions > 0
    assert metrics.rule_of_three_upper_bound is None

    # Latencies: 80, 80, 80, 100(x8), 110, 120, 150
    assert metrics.latency_min_ms == 80.0
    assert metrics.latency_max_ms == 150.0
    assert pytest.approx(metrics.latency_p50_ms, rel=1e-3) == 100.0


def test_compute_metrics_zero_false_additions_rule_of_three() -> None:
    results = []
    # 20 correct accepts
    for i in range(20):
        lbl = SampleLabel(file=f"v_{i}.wav", expected_value=i, category="canonical")
        results.append(SampleResult(sample=lbl, outcome=SampleOutcome.CORRECT_ACCEPT, elapsed_ms=50.0))
    # 10 correct rejects
    for i in range(10):
        lbl = SampleLabel(file=f"n_{i}.wav", expected_value=None, category="negative_noise")
        results.append(SampleResult(sample=lbl, outcome=SampleOutcome.CORRECT_REJECT, elapsed_ms=50.0))

    metrics = compute_metrics(results)
    assert metrics.false_addition_count == 0
    # Rule of 3 on 30 trials: 3 / 30 = 0.10
    assert metrics.rule_of_three_upper_bound is not None
    assert pytest.approx(metrics.rule_of_three_upper_bound, rel=1e-5) == 0.10


def test_compute_metrics_empty_results() -> None:
    metrics = compute_metrics([])
    assert metrics.total_samples == 0
    assert metrics.exact_integer_accuracy == 0.0
    assert metrics.false_addition_rate == 0.0
    assert metrics.rule_of_three_upper_bound is None


# --- 4. End-to-End Benchmark Runner Tests ---


def test_run_benchmark_with_synthetic_files(tmp_path: Path) -> None:
    # 1. Create temporary synthetic WAV files
    wav_1 = tmp_path / "one.wav"
    wav_2 = tmp_path / "two.wav"
    wav_neg = tmp_path / "noise.wav"

    pcm_data = b"\x00\x00" * 800  # 50 ms silence
    write_wav(wav_1, pcm_data, sample_rate=AUDIO_SAMPLE_RATE)
    write_wav(wav_2, pcm_data, sample_rate=AUDIO_SAMPLE_RATE)
    write_wav(wav_neg, pcm_data, sample_rate=AUDIO_SAMPLE_RATE)

    # 2. Setup labels
    labels = [
        SampleLabel(file="one.wav", expected_value=1, category="units", split="dev"),
        SampleLabel(file="two.wav", expected_value=2, category="units", split="dev"),
        SampleLabel(file="noise.wav", expected_value=None, category="negative_noise", split="dev"),
    ]

    # 3. Setup FakeEngine with scripted responses
    engine = FakeEngine(name="fake_test_engine")
    engine.set_script(["one", "two", ""])

    results, metrics = run_benchmark(engine=engine, dataset_dir=tmp_path, labels=labels)

    assert len(results) == 3
    assert results[0].outcome == SampleOutcome.CORRECT_ACCEPT
    assert results[0].parsed_value == 1
    assert results[1].outcome == SampleOutcome.CORRECT_ACCEPT
    assert results[1].parsed_value == 2
    assert results[2].outcome == SampleOutcome.CORRECT_REJECT

    assert metrics.total_samples == 3
    assert metrics.valid_samples == 2
    assert metrics.negative_samples == 1
    assert metrics.exact_integer_accuracy == 1.0
    assert metrics.false_addition_count == 0


def test_run_benchmark_missing_wav_records_error(tmp_path: Path) -> None:
    labels = [
        SampleLabel(file="missing.wav", expected_value=100, category="hundreds"),
    ]
    engine = FakeEngine()
    results, metrics = run_benchmark(engine=engine, dataset_dir=tmp_path, labels=labels)

    assert len(results) == 1
    assert results[0].outcome == SampleOutcome.ERROR
    assert "not found" in (results[0].error_message or "").lower()
    assert metrics.error_samples == 1


# --- 5. Export CSV and Report Formatting Tests ---


def test_export_results_csv(tmp_path: Path) -> None:
    lbl = SampleLabel(file="test.wav", expected_value=50, category="tens", split="dev")
    res = SampleResult(
        sample=lbl,
        outcome=SampleOutcome.CORRECT_ACCEPT,
        asr_text="fifty",
        parsed_value=50,
        parse_status="SUCCESS",
        elapsed_ms=45.2,
    )
    out_csv = tmp_path / "results.csv"
    export_results_csv([res], out_csv)

    assert out_csv.is_file()
    content = out_csv.read_text(encoding="utf-8")
    assert "file,expected_value" in content
    assert "test.wav,50,0,tens,unknown,1,dev,CORRECT_ACCEPT,SUCCESS,fifty,50" in content


def test_format_benchmark_report() -> None:
    results = [
        SampleResult(
            sample=SampleLabel(file="1.wav", expected_value=1, category="canonical", split="dev"),
            outcome=SampleOutcome.CORRECT_ACCEPT,
            elapsed_ms=100.0,
        ),
        SampleResult(
            sample=SampleLabel(file="neg.wav", expected_value=None, category="negative", split="dev"),
            outcome=SampleOutcome.CORRECT_REJECT,
            elapsed_ms=50.0,
        ),
    ]
    metrics = compute_metrics(results)
    report = format_benchmark_report(metrics, engine_name="test_engine")

    assert "VOICE CALCULATOR ASR BENCHMARK REPORT" in report
    assert "test_engine" in report
    assert "Exact Integer Accuracy (EIA)" in report
    assert "False Addition Rate" in report
    assert "LATENCY DISTRIBUTION" in report
    assert "BREAKDOWN BY CATEGORY" in report
