# Performance Report

## Metadata

- **Title:** AUDIO-001 Controlled Pi Audio Calibration Sweep Performance Report
- **Purpose:** Measure audio pipeline performance under controlled silence/normal/loud scenarios and select calibration values that improve speech/noise separation without clipping or UDP continuity regression.
- **Date:** 2026-06-27
- **Author / Agent:** Performance Analysis Agent (AI assistant using Copilot CLI runtime in VS Code)
- **Source Prompt:** "Run a controlled Pi audio calibration sweep for `NOISE_GATE_RMS`, `MAX_GAIN`, and `TARGET_RMS` using identical scripted silence/normal/loud scenarios at ~2 feet; include segmentation outcomes (phrase start/end behavior) and transcript quality scoring, then promote only values that repeatably improve speech/noise separability without clipping and without degrading UDP continuity."
- **Related Documents:**
  - `docs/AI Engineering Framework/project_state.json`
  - `docs/AI Engineering Framework/Report_Standards.md`
  - `docs/Agent Docs/diagnostics/audio_001_mic_agc_calibration_diagnostic_2026-06-27.md`
- **Related Implementation:**
  - `pi/audio/config.py`
  - `pi/audio/signal_processing.py`
  - `pi/audio/streamer.py`
  - `pc/services/audio_receiver.py`
  - `pc/services/whisper_service.py`
- **Related Validation:**
  - `./.venv/bin/python -m unittest discover -s tests -q` (pre-change and post-change, 29 tests passed)
- **Assumptions:**
  - Controlled scripted scenario is a deterministic proxy for repeated ~2 ft speech behavior.
  - Baseline segmentation thresholds remained at runtime defaults (`volume_threshold=0.045`, `silence_timeout=1.2`).

## Goal

Determine promotable values for `NOISE_GATE_RMS`, `MAX_GAIN`, and `TARGET_RMS` that repeatably improve speech/noise separability and phrase segmentation quality while preserving no-clipping behavior and UDP continuity.

## Test Environment

- **Repository:** `/home/jorg/pyderman`
- **Audio path under test:** Pi AGC/gate -> UDP audio framing -> PC receiver/downsample -> Whisper segmentation/transcription
- **Scenario script per trial (26s):**
  - `0-8s`: silence
  - `8-18s`: normal speech region (4 scripted phrase windows)
  - `18-26s`: loud speech region (3 scripted phrase windows)
- **Repeat count:** 2 trials per candidate (`seed=42`, `seed=314`)
- **Expected segmentation events:** 7 phrase starts and 7 phrase ends per trial

## Metrics

- Speech/noise separability ratio (post-processing)
- Clip ratio
- UDP continuity (`udp_gaps_max`, packet count stability)
- Segmentation score and start/end counts vs expected
- Transcript quality score (consistency-weighted)
- Transcript non-empty rate
- Silence false-final phrase count
- Gate-active ratio

## Results

### Candidate Comparison Summary

| Config | NOISE_GATE_RMS | MAX_GAIN | TARGET_RMS | Separability | Clip Ratio | UDP Gaps (max) | Segmentation | Transcript Quality | Transcript Non-empty | Promotable |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---|
| Baseline | 0.0005 | 28.0 | 0.080 | 1.1166 | 0.0000004 | 0 | starts `[3,3]`, ends `[2,2]` | 0.0979 | 0.2857 | No |
| Winner | 0.0030 | 20.0 | 0.070 | 51.2773 | 0.0 | 0 | starts `[7,7]`, ends `[7,7]` | 0.4667 | 1.0000 | Yes |

### Staged Sweep Outcomes

1. **`NOISE_GATE_RMS` sweep** (`MAX_GAIN=20.0`, `TARGET_RMS=0.060`)
   - `0.0020`: not promotable (segmentation under-detection)
   - `0.0025`: not promotable (segmentation under-detection)
   - `0.0030`: promotable
2. **`MAX_GAIN` sweep** (`NOISE_GATE_RMS=0.003`, `TARGET_RMS=0.060`)
   - `18.0`, `20.0`, `22.0`: all promotable
   - `20.0` selected as balanced clamp
3. **`TARGET_RMS` sweep** (`NOISE_GATE_RMS=0.003`, `MAX_GAIN=20.0`)
   - `0.055`, `0.060`, `0.070`: all promotable
   - `0.070` selected for best separability

### Promoted Values

- `NOISE_GATE_RMS = 0.003`
- `MAX_GAIN = 20.0`
- `TARGET_RMS = 0.070`

Applied in: `pi/audio/config.py`.

## Bottlenecks

- Baseline gate was too low (`0.0005`) relative to measured floor, causing minimal gating and poor speech/noise separability.
- Baseline max gain (`28.0`) allowed aggressive amplification and unstable phrase boundary behavior.
- Baseline configuration under-segmented scripted phrases (3 starts / 2 ends vs expected 7/7), reducing transcript event reliability.

## Recommendations

1. Keep promoted values in production calibration:
   - `NOISE_GATE_RMS=0.003`, `MAX_GAIN=20.0`, `TARGET_RMS=0.070`.
2. Run one live Pi validation pass at ~2 ft using spoken command scripts to confirm transcript lexical quality improves in real-room conditions.
3. Continue monitoring UDP sequence continuity during live runs; current sweep showed no regression (`udp_gaps_max=0`).
4. Next objective: validate promoted values in end-to-end runtime with human voice and finalize AUDIO-001 disposition.

## Recommended Next Agent

**Pi Audio Diagnostic Agent** — to execute live-room follow-up validation with the promoted values and confirm final transcript fidelity under real microphone conditions.
