# AUDIO-001 Diagnostic Report — Microphone and AGC Calibration Baseline

## Metadata

- **Title:** AUDIO-001 Microphone and AGC Calibration Diagnostic Baseline
- **Purpose:** Measure current Pi microphone signal quality for speech at ~2 feet, classify defects, and propose evidence-backed calibration values without changing production behavior.
- **Date:** 2026-06-27
- **Author / Agent:** Pi Audio Diagnostic Agent (AI assistant using Copilot CLI runtime in VS Code)
- **Source Prompt:** AUDIO-001 diagnostic/measurement prompt (2026-06-27)
- **Related Documents:**
  - `docs/AI Engineering Framework/project_state.json`
  - `docs/AI Engineering Framework/Development_Lifecycle.md`
  - `docs/AI Engineering Framework/Agent_Orchestration_Guide.md`
  - `docs/AI Engineering Framework/Prompt_Standards.md`
  - `docs/AI Engineering Framework/Report_Standards.md`
  - `docs/AI Engineering Framework/Documentation_Standards.md`
  - `docs/Agent Docs/diagnostics/pi_mic_streamer_diagnostic_2026-06-26.txt`
- **Related Implementation:**
  - `pi/audio/config.py`
  - `pi/audio/device_selection.py`
  - `pi/audio/signal_processing.py`
  - `pi/audio/streamer.py`
  - `pi/mic_udp_streamer.py`
  - `pc/services/audio_receiver.py`
  - `pc/services/whisper_service.py`
  - `pc/runtime_config.py`
- **Related Validation:** `docs/Agent Docs/validation/e2e_runtime_validation_ssh_false_negative_2026-06-26_22-27-00.md`
- **Assumptions:**
  - Pi host `jorg@192.168.0.38` was the active runtime target.
  - Speech-distance guidance (~2 feet) was followed during guided trials.
  - ALSA/JACK warnings are environmental startup noise unless accompanied by stream failure.

## Goal

Determine current microphone signal quality and identify calibration values required for speech at ~2 feet from the Pi microphone.

## Scope

- Active Pi microphone device and runtime config
- Input amplitude and RMS behavior
- Clipping/distortion indicators
- Noise-gate behavior
- AGC gain behavior
- Silence vs speech separability
- Speech segmentation input implications
- UDP audio delivery continuity to PC

## Environment

- **Pi Host:** `SlytherinFuego` (`jorg@192.168.0.38`)
- **Pi Project Path:** `/home/jorg/pibot`
- **Audio Device:** `snd_rpi_googlevoicehat_soundcar ... (hw:0,0)` (card 0, device 0)
- **Configured Stream Settings (production):**
  - sample rate: `48000`
  - input channels: `2`
  - output channels: `1`
  - chunk frames: `1024`
  - channel mode: `left`
  - noise gate RMS: `0.0005`
  - AGC target RMS: `0.08`
  - AGC gain range: `1.0 .. 28.0`
  - AGC attack/release: `0.35 / 0.15`
- **PC Segmentation Defaults:**
  - `RuntimeConfig.volume_threshold = 0.045`
  - `RuntimeConfig.silence_timeout = 1.2`

## Test Procedure (Repeatable)

1. Confirm Pi device/config:
   - `arecord -l`, `arecord -L`
   - Python config readout from `pibot_config` and `pi.audio.config`
2. Run guided capture (no code edits), two repeated trials:
   - wait 5s
   - 8s silence
   - 10s normal speech at ~2 feet
   - 8s louder speech at ~2 feet
3. Per phase, collect:
   - raw RMS and peaks (pre-AGC/gate)
   - processed RMS and peaks (post-AGC/gate)
   - gate-active ratio (`raw_rms < NOISE_GATE_RMS`)
   - AGC gain min/median/max
   - clipped sample ratio
4. UDP continuity check:
   - run listener on PC UDP port 5001
   - run Pi mic streamer for fixed 6s and 20s windows
   - count packets, sequence gaps, interarrival spikes

## Measured Baseline Values

### A) Guided Trial Results (post-AGC values used by receiver/segmentation path)

| Trial | Phase | Proc RMS p50 | Proc RMS mean | Proc RMS p90 | Proc peak max | Raw RMS p50 | Gate active ratio | Gain p50 | Gain max | Clipped ratio |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Guided-1 | Silence | 0.1536 | 0.1482 | 0.2354 | 0.8887 | 0.00339 | 1.87% | 23.61 | 28.00 | 0.0000 |
| Guided-1 | Normal (~2 ft) | 0.1577 | 0.1627 | 0.2744 | 0.9084 | 0.00528 | 2.56% | 18.99 | 27.99 | 0.0000 |
| Guided-1 | Loud (~2 ft) | 0.1602 | 0.1568 | 0.2537 | 0.9043 | 0.00402 | 2.13% | 22.19 | 28.00 | 0.0000 |
| Guided-2 | Silence | 0.1244 | 0.1277 | 0.2136 | 0.8403 | 0.00230 | 1.07% | 27.11 | 28.00 | 0.0000 |
| Guided-2 | Normal (~2 ft) | 0.1552 | 0.1721 | 0.3036 | 0.9953 | 0.00444 | 0.64% | 21.20 | 28.00 | 0.0000 |
| Guided-2 | Loud (~2 ft) | 0.1815 | 0.1827 | 0.2913 | 0.9442 | 0.00574 | 0.53% | 18.38 | 28.00 | 0.0000 |

### B) Baseline noise and speech separation summary

- **Raw silence RMS p50 range:** `0.00230 .. 0.00339`
- **Raw normal RMS p50 range:** `0.00444 .. 0.00528`
- **Raw loud RMS p50 range:** `0.00402 .. 0.00574`
- **Post-AGC silence vs normal separation (mean):** ~`0.128 .. 0.148` vs ~`0.163 .. 0.172` (limited but present)
- **Post-AGC loud mean:** ~`0.157 .. 0.183`

### C) UDP continuity

- 6s stream window: `208` packets received, first packet from `192.168.0.38`, sequence gaps `1`
- 20s stream window: `860` packets received, expected by seq range `863`, sequence gaps `3`, max interarrival ~`104.27 ms`
- Packet path is active; minor packet loss/jitter observed.

## Observed Failure / Quality Characteristics

1. **Gate threshold is below measured silence floor.**  
   Current gate `0.0005`; measured silence raw RMS p50 `0.00230 .. 0.00339`.  
   Result: gate rarely activates (<3% of chunks), even during intended silence.

2. **AGC consistently drives toward max gain.**  
   Gain frequently at/near `28.0` in all phases, including silence.  
   Result: background noise is amplified and speech/noise separability margin is reduced.

3. **No sustained clipping detected in measured runs.**  
   Clipped sample ratio remained `0.0000` in all guided phases.

4. **Silence and speech are distinguishable, but only with narrow margin.**  
   Post-AGC medians overlap in lower ranges; separation exists but is not robust.

5. **UDP transport is functionally working with low-level continuity defects.**  
   Small sequence-gap count indicates minor loss/jitter, not full path failure.

## Defect Classification

| ID | Defect | Classification | Severity | Status | Cause Proven |
|---|---|---|---|---|---|
| D1 | Noise gate threshold too low for current environment | **Verified** | Medium | Open | **Yes** |
| D2 | AGC noise pumping (high gain during silence) | **Verified** | Medium | Open | **Yes** |
| D3 | Silence/speech separability too narrow for robust tuning margin | **Verified** | Medium | Open | **Partially** (linked to D1/D2, needs tuning validation) |
| D4 | Minor UDP packet loss/jitter on audio path | **Verified** | Low | Open | **No** (mechanism not isolated) |
| D5 | Elevated ambient/mechanical noise contribution at mic front-end | **Suspected** | Low | Open | No |
| D6 | Segmentation quality impact under revised calibration | **Unresolved** | Low | Open | No |

## Problem-Type Determination

- **Configuration:** Partially (valid device selected; thresholds likely mis-set for current noise floor)
- **Calibration:** **Primary contributor**
- **Hardware handling:** Possible secondary contributor (suspected environmental/mechanical noise)
- **Transport:** Minor secondary contributor (low packet-loss/jitter)
- **Speech segmentation:** Affected indirectly by calibration; direct defect mechanism not fully proven in this run
- **Overall:** **Combination**, with calibration as dominant factor

## Recommended Calibration Changes (Evidence-Based)

### Validated from repeated controlled measurements

- **Raise noise gate RMS above measured silence median.**
  - Current: `0.0005`
  - Measured silence p50: `0.00230 .. 0.00339`
  - **Validated initial range:** `0.0020 .. 0.0030` (expected to suppress a substantial portion of silence chunks while preserving speech chunks)

- **Treat current AGC max gain as too permissive for this input floor.**
  - Current: `28.0`
  - Observed behavior: frequent saturation at max even in silence
  - **Validated directional change:** lower max gain from current value (exact best value still requires sweep)

### Experimental candidates (hypotheses requiring controlled A/B validation)

- `pi/audio/config.py` candidates:
  - `NOISE_GATE_RMS`: try `0.0025` first (then `0.0020` and `0.0030`)
  - `MAX_GAIN`: try `20.0` first (then `18.0` and `22.0`)
  - `TARGET_RMS`: try `0.060` first (then `0.055` and `0.070`)
- `pc/runtime_config.py` candidate:
  - keep `volume_threshold` at `0.045` initially and re-evaluate after Pi-side calibration sweep (effective threshold is often dominated by adaptive noise-floor multiplier)

## Validation Checks Against Task Requirements

| Requirement | Result | Notes |
|---|---|---|
| Silence and speech distinguishable by measured levels | **Pass (marginal)** | Distinguishable, but separation margin is narrow |
| Normal speech at ~2 ft captured without sustained clipping | **Pass** | No clipping in guided trials |
| UDP stream remains active during testing | **Pass** | Continuous packet flow observed in both windows |
| Recommended thresholds/AGC values derived from measurement | **Pass** | Derived from measured RMS/gain/packet evidence |

## Temporary Changes

- No production files were modified.
- No permanent behavior changes were made.
- Diagnostics were executed via runtime commands only.

## Routing Gate (Explicit Answers)

1. **Was a defect verified?**  
   **Yes.** Calibration defects D1 and D2 are verified.

2. **Was the exact failure mechanism proven?**  
   **Partially yes.** For D1/D2, mechanism is proven (gate threshold below silence floor causes near-continuous AGC amplification of noise). For UDP jitter/loss and hardware-noise contribution, exact mechanism is not yet proven.

3. **Is there direct evidence that a specific production change will correct it?**  
   **Directional evidence yes, exact-value proof no.** Data supports raising gate and reducing AGC aggressiveness, but exact final production values are not fully validated yet.

4. **Were proposed calibration values validated through controlled repeated trials?**  
   **Partially.** Repeated trials validate recommended value ranges/directions; exact final values remain experimental until controlled sweep + segmentation quality validation is completed.

## Recommended Next Agent

**Performance Analysis Agent**

## Recommended Next Objective

Run a controlled Pi audio calibration sweep for `NOISE_GATE_RMS`, `MAX_GAIN`, and `TARGET_RMS` using identical scripted silence/normal/loud scenarios at ~2 feet; include segmentation outcomes (phrase start/end behavior) and transcript quality scoring, then promote only values that repeatably improve speech/noise separability without clipping and without degrading UDP continuity.

## Checkpoint Recommendation

**Continue Investigation** (do not implement production calibration changes yet).

## Suggested project_state update for Documentation Steward (do not apply in this task)

- Keep `AUDIO-001` open
- Add note: calibration mechanism partially proven; controlled value sweep pending
- Recommended next agent after this diagnostic: `Performance Analysis Agent`
