# Error Taxonomy Audit & Containment Verification

> **Evaluation Dataset:** `data/processed_phone/benchmark_dad/` (62 segmented prompts, 61 eligible, Prompt 16 excluded).
> **Engines:** Vosk CPU (Phase 4C natural parser) vs `faster-whisper-tiny.en` CPU (2 threads, `int8`).

---

## 1. Error Taxonomy Breakdown

| Taxonomy Category | Vosk CPU (N=61) | faster-whisper tiny.en (N=61) | Description |
| :--- | :---: | :---: | :--- |
| **CORRECT** | 35 (57.4%) | 38 (62.3%) | Exact integer match with intended value |
| **BARE_FORM_TRAP** | 2 (3.3%) | 0 (0.0%) | Bare hundred/thousand grammar correctly parsed transcript, but ASR dropped spoken multiplier |
| **CONFUSABLE_PAIR** | 4 (6.6%) | 1 (1.6%) | Acoustic phonetic confusion between -teen / -ty or similar digits |
| **HALLUCINATED_DIGITS** | 0 (0.0%) | 3 (4.9%) | ASR hallucinated multi-digit sequences or corrupted numbers from noise/speech |
| **PARSER_REJECTION_AMBIGUOUS** | 1 (1.6%) | 0 (0.0%) | Colloquial ambiguity or missing scale rejected by parser |
| **PARSER_REJECTION_EMPTY** | 7 (11.5%) | 4 (6.6%) | ASR produced empty/silence transcript |
| **PARSER_REJECTION_MALFORMED** | 8 (13.1%) | 2 (3.3%) | Malformed compound multiplier or structural grammar error rejected by parser |
| **PARSER_REJECTION_MULTIPLE_NUMBERS** | 3 (4.9%) | 3 (4.9%) | Digit-by-digit or disconnected number sequence rejected by parser |
| **PARSER_REJECTION_NOT_A_NUMBER** | 0 (0.0%) | 5 (8.2%) | Out-of-vocabulary or corrupted acoustic tokens rejected by parser |
| **PARSER_REJECTION_OUT_OF_RANGE** | 0 (0.0%) | 1 (1.6%) | Value exceeds 2000 bound rejected by parser |
| **WORD_DROP** | 1 (1.6%) | 4 (6.6%) | ASR dropped leading scale/multiplier (e.g. 'thousand', 'hundred', 'two') |

---

## 2. Detailed Per-Category Examples

### Category: `BARE_FORM_TRAP`
- **Vosk Examples:**
  * `Prompt 43` (Intended: 1250): Transcript `"hundred fifteen"` $\rightarrow$ Parsed: `115` | *Spoke 'twelve hundred fifty' (1250), ASR transcribed 'hundred fifteen' -> parsed as 115*
  * `Prompt 48` (Intended: 2000): Transcript `"thousand"` $\rightarrow$ Parsed: `1000` | *Spoke 'two thousand' (2000), ASR dropped 'two' -> transcript 'thousand' parsed as 1000*

### Category: `CONFUSABLE_PAIR`
- **Vosk Examples:**
  * `Prompt 07` (Intended: 15): Transcript `"ten"` $\rightarrow$ Parsed: `10` | *Acoustic confusion on confusable/tens (15 vs 10) -> parsed as 10*
  * `Prompt 14` (Intended: 70): Transcript `"eighty"` $\rightarrow$ Parsed: `80` | *Acoustic confusion on confusable/tens (70 vs 80) -> parsed as 80*
  * `Prompt 22` (Intended: 47): Transcript `"thirty seven"` $\rightarrow$ Parsed: `37` | *Acoustic confusion on confusable/tens (47 vs 37) -> parsed as 37*
  * `Prompt 61` (Intended: 60): Transcript `"sixteen"` $\rightarrow$ Parsed: `16` | *Acoustic confusion on confusable/tens (60 vs 16) -> parsed as 16*
- **faster-whisper tiny.en Examples:**
  * `Prompt 53` (Intended: 35): Transcript `"85."` $\rightarrow$ Parsed: `85` | *Acoustic confusion on confusable/tens (35 vs 85) -> parsed as 85*

### Category: `HALLUCINATED_DIGITS`
- **faster-whisper tiny.en Examples:**
  * `Prompt 12` (Intended: 60): Transcript `"660."` $\rightarrow$ Parsed: `660` | *Spoke number/compound, ASR produced multi-digit string '660.' -> parsed as 660*
  * `Prompt 18` (Intended: 90): Transcript `"990."` $\rightarrow$ Parsed: `990` | *Spoke number/compound, ASR produced multi-digit string '990.' -> parsed as 990*
  * `Prompt 26` (Intended: 80): Transcript `"808"` $\rightarrow$ Parsed: `808` | *Spoke number/compound, ASR produced multi-digit string '808' -> parsed as 808*

### Category: `PARSER_REJECTION_AMBIGUOUS`
- **Vosk Examples:**
  * `Prompt 12` (Intended: 60): Transcript `"six sixty"` $\rightarrow$ Parsed: `` | *Ambiguous compound/repetition in transcript 'six sixty'*

### Category: `PARSER_REJECTION_EMPTY`
- **Vosk Examples:**
  * `Prompt 20` (Intended: 25): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 21` (Intended: 35): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 25` (Intended: 75): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 27` (Intended: 95): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 36` (Intended: 500): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 53` (Intended: 35): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 58` (Intended: 175): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
- **faster-whisper tiny.en Examples:**
  * `Prompt 06` (Intended: 12): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 07` (Intended: 15): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 28` (Intended: 100): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*
  * `Prompt 51` (Intended: 80): Transcript `""` $\rightarrow$ Parsed: `` | *ASR produced empty transcript*

### Category: `PARSER_REJECTION_MALFORMED`
- **Vosk Examples:**
  * `Prompt 10` (Intended: 50): Transcript `"[unk] zero"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript '[unk] zero'*
  * `Prompt 18` (Intended: 90): Transcript `"nine nine zero ninety"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'nine nine zero ninety'*
  * `Prompt 26` (Intended: 80): Transcript `"eight zero eighty"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'eight zero eighty'*
  * `Prompt 31` (Intended: 125): Transcript `"hundred [unk]"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'hundred [unk]'*
  * `Prompt 37` (Intended: 750): Transcript `"seven [unk] fifty"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'seven [unk] fifty'*
  * `Prompt 45` (Intended: 1750): Transcript `"seventy hundred fifty"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'seventy hundred fifty'*
  * `Prompt 47` (Intended: 1999): Transcript `"ninety hundred ninety nine"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'ninety hundred ninety nine'*
  * `Prompt 57` (Intended: 110): Transcript `"[unk] ten"` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript '[unk] ten'*
- **faster-whisper tiny.en Examples:**
  * `Prompt 10` (Intended: 50): Transcript `"by 0."` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'by 0.'*
  * `Prompt 57` (Intended: 110): Transcript `"in 10."` $\rightarrow$ Parsed: `` | *Structural scale or grammar malformation in transcript 'in 10.'*

### Category: `PARSER_REJECTION_MULTIPLE_NUMBERS`
- **Vosk Examples:**
  * `Prompt 05` (Intended: 10): Transcript `"one zero"` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript 'one zero'*
  * `Prompt 06` (Intended: 12): Transcript `"one two"` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript 'one two'*
  * `Prompt 08` (Intended: 19): Transcript `"one nine"` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript 'one nine'*
- **faster-whisper tiny.en Examples:**
  * `Prompt 05` (Intended: 10): Transcript `"1 0."` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript '1 0.'*
  * `Prompt 08` (Intended: 19): Transcript `"1 9."` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript '1 9.'*
  * `Prompt 37` (Intended: 750): Transcript `"7 7 5 0 7 50."` $\rightarrow$ Parsed: `` | *Digit-by-digit or disconnected numbers in transcript '7 7 5 0 7 50.'*

### Category: `PARSER_REJECTION_NOT_A_NUMBER`
- **faster-whisper tiny.en Examples:**
  * `Prompt 03` (Intended: 5): Transcript `"Bye."` $\rightarrow$ Parsed: `` | *Out-of-vocabulary or corrupted phonemes in transcript 'Bye.'*
  * `Prompt 04` (Intended: 9): Transcript `"main"` $\rightarrow$ Parsed: `` | *Out-of-vocabulary or corrupted phonemes in transcript 'main'*
  * `Prompt 14` (Intended: 70): Transcript `"8p."` $\rightarrow$ Parsed: `` | *Out-of-vocabulary or corrupted phonemes in transcript '8p.'*
  * `Prompt 21` (Intended: 35): Transcript `"got a defi."` $\rightarrow$ Parsed: `` | *Out-of-vocabulary or corrupted phonemes in transcript 'got a defi.'*
  * `Prompt 41` (Intended: 1100): Transcript `"Hello hello red."` $\rightarrow$ Parsed: `` | *Out-of-vocabulary or corrupted phonemes in transcript 'Hello hello red.'*

### Category: `PARSER_REJECTION_OUT_OF_RANGE`
- **faster-whisper tiny.en Examples:**
  * `Prompt 47` (Intended: 1999): Transcript `"99999."` $\rightarrow$ Parsed: `` | *Transcript parsed to out-of-range value (>2000) in '99999.'*

### Category: `WORD_DROP`
- **Vosk Examples:**
  * `Prompt 32` (Intended: 150): Transcript `"fifty"` $\rightarrow$ Parsed: `50` | *Spoke 'hundred fifty' (150), ASR dropped 'hundred' -> transcript 'fifty' parsed as 50*
- **faster-whisper tiny.en Examples:**
  * `Prompt 40` (Intended: 1050): Transcript `"150."` $\rightarrow$ Parsed: `150` | *Spoke thousands/compound (1050), ASR dropped leading thousand/multiplier -> transcript '150.' parsed as 150*
  * `Prompt 42` (Intended: 1200): Transcript `"200."` $\rightarrow$ Parsed: `200` | *Spoke thousands/compound (1200), ASR dropped leading thousand/multiplier -> transcript '200.' parsed as 200*
  * `Prompt 43` (Intended: 1250): Transcript `"250."` $\rightarrow$ Parsed: `250` | *Spoke thousands/compound (1250), ASR dropped leading thousand/multiplier -> transcript '250.' parsed as 250*
  * `Prompt 45` (Intended: 1750): Transcript `"750."` $\rightarrow$ Parsed: `750` | *Spoke thousands/compound (1750), ASR dropped leading thousand/multiplier -> transcript '750.' parsed as 750*

---

## 3. Engine Complementarity Table

This table establishes empirical overlap and unique successes between Vosk and faster-whisper on the identical 61 eligible Dad utterances. This serves as primary input to ADR-001 in Phase 5C.

- **Both Engines Correct:** 28 / 61 (45.9%)
- **Vosk Only Correct:** 7 / 61 (11.5%)
- **faster-whisper Only Correct:** 10 / 61 (16.4%)
- **Both Engines Failed/Rejected:** 16 / 61 (26.2%)
- **Theoretical Oracle Upper Bound (Vosk $\cup$ Whisper):** 45 / 61 (73.8%)

| Classification | Count | Prompt IDs & Intended Values |
| :--- | :---: | :--- |
| **Both Correct** | 28 | P01 (0), P02 (1), P09 (15), P11 (16), P13 (17), P15 (18), P17 (19), P19 (21), P23 (50), P24 (65), P29 (105), P30 (110), P33 (175), P34 (200), P35 (250), P38 (999), P39 (1000), P44 (1500), P46 (1900), P49 (47), P50 (125), P52 (1500), P54 (200), P55 (75), P56 (50), P59 (1000), P60 (25), P62 (1500) |
| **Vosk Only Correct** | 7 | P03 (5), P04 (9), P28 (100), P40 (1050), P41 (1100), P42 (1200), P51 (80) |
| **faster-whisper Only Correct** | 10 | P20 (25), P22 (47), P25 (75), P27 (95), P31 (125), P32 (150), P36 (500), P48 (2000), P58 (175), P61 (60) |
| **Both Failed / Rejected** | 16 | P05 (10), P06 (12), P07 (15), P08 (19), P10 (50), P12 (60), P14 (70), P18 (90), P21 (35), P26 (80), P37 (750), P43 (1250), P45 (1750), P47 (1999), P53 (35), P57 (110) |

---

## 4. Containment Verification for Wrong Parsed Values

Under project rules (`rules.md` §C.12 and `prd.md` FR-3), every wrong recognized number must be safely contained by the decision layer to prevent silent false additions.

| Prompt ID | Engine | Intended Value | Raw Transcript | Parsed Value | Safe Mode Decision | Fast Mode Decision (Uncalibrated) | Auto-Added? | Containment Status |
| :---: | :--- | :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| `P07` | `vosk` | 15 | `"ten"` | **10** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P12` | `faster-whisper-tiny` | 60 | `"660."` | **660** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P14` | `vosk` | 70 | `"eighty"` | **80** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P18` | `faster-whisper-tiny` | 90 | `"990."` | **990** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P22` | `vosk` | 47 | `"thirty seven"` | **37** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P26` | `faster-whisper-tiny` | 80 | `"808"` | **808** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P32` | `vosk` | 150 | `"fifty"` | **50** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P40` | `faster-whisper-tiny` | 1050 | `"150."` | **150** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P42` | `faster-whisper-tiny` | 1200 | `"200."` | **200** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P43` | `vosk` | 1250 | `"hundred fifteen"` | **115** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P43` | `faster-whisper-tiny` | 1250 | `"250."` | **250** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P45` | `faster-whisper-tiny` | 1750 | `"750."` | **750** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P48` | `vosk` | 2000 | `"thousand"` | **1000** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P53` | `faster-whisper-tiny` | 35 | `"85."` | **85** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |
| `P61` | `vosk` | 60 | `"sixteen"` | **16** | `CONFIRM` | `CONFIRM` (conf=None) | **NO** | **PASS (Safely Contained)** |

### Containment Finding:
- **Total Wrong Parsed Values Evaluated:** 15 cases (7 Vosk, 8 faster-whisper).
- **Auto-Added to Running Total:** **0 / 15 (0.0%)**.
- **Containment Mechanism:** Safe Mode enforces manual confirmation for 100% of candidate parses. Fast Mode gates automated addition behind calibrated confidence (`auto_accept_enabled=True` and `confidence >= min_confidence`), so uncalibrated confidence (`confidence=None`) deterministically forces manual confirmation.
- **Verdict:** **Zero False Additions. Containment is 100% verified across all benchmarked models.**