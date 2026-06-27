# Diagnostic Report

## Metadata

- **Title:** AUDIO-001 Microphone and AGC Calibration Diagnostic Baseline
- **Purpose:** Establish a reproducible measured baseline for Pi microphone signal quality and derive evidence-based calibration targets for speech at ~2 feet.
- **Date:** 2026-06-27
- **Author / Agent:** Pi Audio Diagnostic Agent (Copilot CLI runtime)
- **Source Prompt:** Pi Audio Diagnostic Agent task for backlog item `AUDIO-001` (2026-06-27)
- **Related Documents:**
  - `docs/AI Engineering Framework/project_state.json`
  - `docs/AI Engineering Framework/Development_Lifecycle.md`
  - `docs/AI Engineering Framework/Agent_Orchestration_Guide.md`
  - `docs/AI Engineering Framework/Prompt_Standards.md`
  - `docs/AI Engineering Framework/Report_Standards.md`
  - `docs/AI Engineering Framework/Documentation_Standards.md`
- **Related Implementation:**
  - `pi/audio/config.py`
  - `pi/audio/signal_processing.py`
  - `pi/audio/streamer.py`
  - `pi/audio/device_selection.py`
  - `pi/mic_udp_streamer.py`
  - `pc/services/audio_receiver.py`
  - `pc/services/whisper_service.py`
  - `pc/runtime_config.py`
- **Related Validation:** None (diagnostic measurement task)
- **Assumptions:**
  - Operator-provided speech samples were delivered at approximately the requested distance/volume.
  - Pi and PC hosts matched current runtime settings (`PIBOT_PI_HOST=192.168.0.38`, `PIBOT_PC_HOST=192.168.0.189`).

## Goal

Determine current microphone signal quality and identify calibration values for speech at ~2 feet without permanently changing production behavior.

## Scope

- Active Pi microphone capture path: device selection, format/rate/channels, channel selection, AGC, noise gate, PCM conversion.
- PC-side ingest and segmentation inputs: UDP receive continuity, RMS behavior versus speech threshold logic.
- Diagnostics only (no permanent implementation change).

## Environment

- **Pi Host:** `jorg@192.168.0.38` (`SlytherinFuego`)
- **Pi Audio Device:** `snd_rpi_googlevoicehat_soundcar ... (hw:0,0)` (selected index `0`)
- **ALSA capture hardware:** Google voiceHAT card 0 device 0
- **Pi stream settings:** 48 kHz, `paInt32`, 2 input channels, 1024 frames/chunk
- **Audio processing settings (current):**
  - `CHANNEL_MODE=left`
  - `NOISE_GATE_RMS=0.0005`
  - `TARGET_RMS=0.08`
  - `MIN_GAIN=1.0`
  - `MAX_GAIN=28.0`
  - `AGC_ATTACK=0.35`
  - `AGC_RELEASE=0.15`
- **PC segmentation settings (current):**
  - `RuntimeConfig.volume_threshold=0.045`
  - `RuntimeConfig.silence_timeout=1.2`
  - Whisper effective threshold logic: `max(volume_threshold, noise_floor * 1.35)`

## Test Procedure (Repeatable)

1. Confirm Pi audio config + selected device via `pyaudio` and `select_input_device`.
2. Verify ALSA capture controls (`amixer get Capture`, `amixer get Master`).
3. For each stage, run a 10-second capture script on Pi that:
   - reads raw int32 input
   - applies current channel select + AGC/gate path
   - computes raw RMS, processed RMS, peak, clipping, gate activation, gain behavior
   - sends UDP audio packets to PC (`5001`)
4. Simultaneously run a PC-side UDP listener to record packet continuity and receive-side RMS/peak.
5. Stages:
   - Stage A: room silence
   - Stage B: normal speech at ~2 ft
   - Stage C: louder speech at ~2 ft
6. Run additional 10-second channel check for left vs right raw RMS dominance.

## Measured Baseline Values

### Runtime/device facts

- `pibot.env` present and aligned with expected hosts/ports.
- Selected mic device is index 0 (Google voiceHAT).
- ALSA capture level: `Capture 100%` (both channels on).
- Right channel measured as effectively zero in channel-check run.

### Stage metrics (Pi-side processing path)

| Stage | Chunks | Raw RMS p50 | Raw RMS p95 | Processed RMS p50 | Processed RMS p95 | Processed RMS max | Peak max | Gate ratio | Gain p50 | Gain end | Clipping |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Silence | 469 | 0.001402 | 0.007139 | 0.075961 | 0.258492 | 0.481202 | 0.943817 | 32.6% | 20.916 | 25.394 | none |
| Normal (~2 ft) | 469 | 0.000965 | 0.003745 | 0.054651 | 0.185904 | 0.397230 | 0.848572 | 31.3% | 26.339 | 8.290 | none |
| Loud (~2 ft) | 469 | 0.000560 | 0.002104 | 0.030168 | 0.105353 | 0.322584 | 0.668762 | 34.3% | 25.193 | 20.436 | none |

### UDP continuity metrics (PC-side listener during each stage)

| Stage | UDP packets (10s window) | RMS p50 | RMS p95 | RMS max | Peak max | Gap count (>60 ms) | Max gap |
|---|---:|---:|---:|---:|---:|---:|---:|
| Silence | 467 | 0.075106 | 0.258697 | 0.481202 | 0.943817 | 10 | 0.1446 s |
| Normal (~2 ft) | 468 | 0.054338 | 0.186028 | 0.397230 | 0.848572 | 3 | 0.1080 s |
| Loud (~2 ft) | 469 | 0.030168 | 0.105353 | 0.322584 | 0.668762 | 7 | 0.1186 s |

### Channel check (10s normal speech sample)

- Left RMS p50: `0.001028`, p95: `0.002968`, max: `0.061125`
- Right RMS p50/p95/max: `0.0 / 0.0 / 0.0`
- Stronger-channel ratio: left `100%` (469/469 chunks)

## Observed Failure / Quality Characteristics

### Verified facts

1. Silence and speech are **not cleanly separable** in the current processed stream:
   - Silence processed RMS p50 (`0.075961`) is higher than normal speech (`0.054651`) and loud speech (`0.030168`).
2. AGC frequently drives high gain in all stages (median gain ~21–26x), amplifying ambient/noise floor substantially.
3. Noise gate still activates for ~31–34% of chunks during speech stages, indicating weak/unstable input relative to gate threshold.
4. No clipping evidence was observed (clip ratios zero in all stage runs).
5. UDP transport remained active and continuous enough for real-time use:
   - packet counts match expected ~46.9 packets/s
   - no sustained transport dropouts in the active 10s windows.
6. Right channel is effectively dead; left channel carries all measurable signal.
7. One transient stream-open error (`Invalid audio channels`) occurred during one loud run and cleared on retry.

### Inferences (from measured facts)

1. Primary issue is not packet transport; it is pre-segmentation signal conditioning (mic level + AGC/gate interaction).
2. Current AGC target/max gain settings over-amplify room baseline, collapsing speech-vs-silence contrast used by segmentation.
3. The loudness ordering inversion (silence > normal > loud in processed p50) indicates unstable capture dynamics and/or microphone orientation/hardware handling effects.

## Problem Classification (Task Requirement #5)

- **Configuration:** Yes (AGC/gate/threshold values currently misaligned with measured input behavior).
- **Calibration:** Yes (current values do not preserve speech/silence separability at ~2 ft).
- **Hardware handling:** Likely yes (transient stream-open fault + very weak raw signal + right channel flatline).
- **Transport (UDP):** No primary defect observed.
- **Speech segmentation inputs:** Yes (current RMS distribution conflicts with threshold strategy).
- **Overall:** **Combination** of calibration + configuration + probable hardware-handling factors.

## Recommended Calibration Changes (Evidence-Based)

Apply as a controlled calibration patch (not during this diagnostic run):

1. `NOISE_GATE_RMS`: **0.0005 -> 0.0002**
   - Justification: speech raw RMS p50 values are near current threshold; lower gate should reduce false suppression during weak speech.
2. `TARGET_RMS`: **0.08 -> 0.05**
   - Justification: current target plus high gain produces silence RMS similar to/above speech.
3. `MAX_GAIN`: **28.0 -> 12.0**
   - Justification: measured median gain ~21–26x indicates aggressive amplification of baseline noise.
4. `AGC_ATTACK`: **0.35 -> 0.20**
   - Justification: slower gain rise should reduce rapid noise pumping.
5. `AGC_RELEASE`: **0.15 -> 0.10**
   - Justification: moderate release to reduce unstable gain swings after transients.
6. Keep `CHANNEL_MODE="left"` for now (right channel measured at zero), but include hardware verification of microphone wiring/orientation as part of next objective.
7. Re-tune segmentation threshold only after AGC/gate recalibration:
   - Initial post-calibration trial target for `RuntimeConfig.volume_threshold`: **0.030–0.040**, selected from new measured silence/speech separation (must be re-measured).

## Validation Against Requested Criteria

- **Silence vs speech distinguishable?** **Fail** under current calibration (measured overlap/inversion).
- **Normal speech at ~2 ft without sustained clipping?** **Pass** for clipping (none observed), **Fail** for quality/separability.
- **UDP stream active during testing?** **Pass** (expected packet rate and active continuity in each stage).
- **Recommendations derived from measurements?** **Pass** (all values tied to captured RMS/gain/gate distributions).

## Temporary Changes

- No repository code/config files were permanently modified.
- Temporary diagnostic scripts were executed over SSH and not retained in the repository.

## Whether Implementation Changes Are Required

**Yes.** A targeted calibration implementation is required in `pi/audio/config.py` (and follow-up validation), plus a short hardware-handling check for microphone capture stability.

## Remaining Defects

- **High:** Speech/silence separability failure for current mic pipeline at ~2 ft (blocks reliable segmentation quality).
- **Medium:** Probable hardware-handling instability (`Invalid audio channels` transient open failure).
- **Low:** Persistent ALSA/JACK warning noise during device enumeration (non-blocking but diagnostic noise).

## Recommended Next Agent

**Runtime Implementation Agent**

## Recommended Next Objective

Implement the above calibration values in a narrow change set, then run a follow-up validation pass with the same 3-stage procedure to verify:

1. silence RMS is materially below speech RMS,
2. normal speech at ~2 ft remains non-clipping,
3. gate activation during speech is reduced,
4. segmentation threshold can be set from measured post-calibration distributions.

## Checkpoint Recommendation

**Continue Implementation** (do not checkpoint this item yet).

## Project-State Note for Documentation Steward

Do **not** update `docs/AI Engineering Framework/project_state.json` in this task.  
After post-calibration validation completes, update `AUDIO-001` status/severity and latest diagnostic/validation artifact references accordingly.
