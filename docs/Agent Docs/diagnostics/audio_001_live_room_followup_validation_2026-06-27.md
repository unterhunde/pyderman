# Diagnostic Report

## Metadata

- **Title:** AUDIO-001 Live-Room Follow-up Validation (Promoted Calibration)
- **Purpose:** Validate microphone/AGC behavior and transcript fidelity under real microphone conditions (~2 ft speech) using promoted calibration values.
- **Date:** 2026-06-27
- **Author / Agent:** Pi Audio Diagnostic Agent (AI assistant using Copilot CLI runtime in VS Code)
- **Source Prompt:** "execute live-room follow-up validation with the promoted values and confirm final transcript fidelity under real microphone conditions. for backlog item AUDIO-001."
- **Related Documents:**
  - `docs/AI Engineering Framework/project_state.json`
  - `docs/AI Engineering Framework/Development_Lifecycle.md`
  - `docs/AI Engineering Framework/Agent_Orchestration_Guide.md`
  - `docs/AI Engineering Framework/Prompt_Standards.md`
  - `docs/AI Engineering Framework/Report_Standards.md`
  - `docs/AI Engineering Framework/Documentation_Standards.md`
  - `docs/Agent Docs/diagnostics/audio_001_calibration_sweep_2026-06-27.md`
- **Related Implementation:**
  - `pi/audio/config.py`
  - `pi/audio/signal_processing.py`
  - `pi/audio/streamer.py`
  - `pi/audio/device_selection.py`
  - `pc/services/audio_receiver.py`
  - `pc/services/whisper_service.py`
  - `pc/runtime_config.py`
- **Related Validation:** Live-room runtime command measurements on Pi host `jorg@192.168.0.38` and PC host `192.168.0.189`.
- **Assumptions:**
  - Human speech was performed at approximately two feet from the Pi microphone during prompted phases.
  - Promoted values under test: `NOISE_GATE_RMS=0.003`, `TARGET_RMS=0.070`, `MAX_GAIN=20.0`.

## Goal

Determine current microphone signal quality and required calibration for ~2 ft speech, including gate/AGC behavior, clipping risk, silence detection separation, and UDP/transcript fidelity.

## Scope

- Microphone device selection and active runtime settings
- Sample rate/channels
- Input amplitude, RMS, clipping
- Noise-gate and AGC behavior
- Silence detection / speech segmentation inputs
- UDP audio continuity to PC
- Final transcript fidelity under real microphone conditions

## Environment

- **Pi host:** `SlytherinFuego` (`jorg@192.168.0.38`)
- **Active capture device:** `snd_rpi_googlevoicehat_soundcar ... (hw:0,0)` (card 0, device 0)
- **Pi active runtime config (from active `/home/jorg/pibot`):**
  - `pi_sample_rate=48000`
  - `INPUT_CHANNELS=2`, `OUTPUT_CHANNELS=1`, `CHUNK_FRAMES=1024`, `CHANNEL_MODE=left`
  - **Active file values:** `NOISE_GATE_RMS=0.0005`, `TARGET_RMS=0.08`, `MAX_GAIN=28.0`
- **PC receiver/transcription path under test:** UDP `:5001` -> resample to 16 kHz -> Whisper transcription
- **Segmentation defaults inspected:** `volume_threshold=0.045`, `silence_timeout=1.2`

## Test Procedure (Repeatable)

1. Confirm active Pi device and runtime settings (`arecord -l`, python config readout on Pi).
2. Run promoted-value diagnostic trials (temporary in-process override only; no file edits):
   - Silence phase (~10 s)
   - Normal speech phrase at ~2 ft
   - Louder speech phrase at ~2 ft
3. For speech phases, simultaneously:
   - stream UDP audio to PC
   - measure Pi-side raw/proc RMS, gain, gate activation, clipping
   - measure PC-side UDP continuity and transcription output
4. Compare measured levels against segmentation thresholds and transcript fidelity expectations.

## Measured Baseline / Follow-up Values

### 1) Silence phase (promoted values, Pi-side, 10 s)

- `raw_rms_p50=0.000834`, `raw_rms_p90=0.001730`
- `proc_rms_p50=0.000137`, `proc_rms_p90=0.000298`
- `gate_active_ratio=0.9616`
- `gain_p50=1.0`, `gain_max=11.44`
- `proc_peak_max=0.3523`
- `clip_ratio=0.00000000`

### 2) Normal speech phase (promoted values, Pi-side, 12 s)

- `raw_rms_p50=0.001897`, `raw_rms_p90=0.005462`
- `proc_rms_p50=0.000328`, `proc_rms_p90=0.131190`
- `gate_active_ratio=0.6945`
- `gain_p50=9.7630`, `gain_max=16.8839`
- `proc_peak_max=0.5308`
- `clip_ratio=0.00000000`

### 3) Louder speech phase (promoted values, Pi-side, 12 s)

- `raw_rms_p50=0.001321`, `raw_rms_p90=0.002992`
- `proc_rms_p50=0.000225`, `proc_rms_p90=0.038850`
- `gate_active_ratio=0.8988`
- `gain_p50=3.4740`, `gain_max=18.1841`
- `proc_peak_max=0.4178`
- `clip_ratio=0.00000000`

### 4) Continuous normal speech confirmation run (promoted values, Pi-side, 20 s)

- `raw_rms_p50=0.001922`, `raw_rms_p90=0.003740`
- `proc_rms_p50=0.000333`, `proc_rms_p90=0.119672`
- `gate_active_ratio=0.7452`
- `gain_p50=10.4391`, `gain_max=19.6129`
- `proc_peak_max=0.4343`
- `clip_ratio=0.00000000`

### 5) UDP continuity and transcript fidelity (PC-side captures)

- Continuous normal run:
  - `UDP_PACKETS=723`
  - `UDP_SEQ_GAPS=5` (`UDP_MAX_SEQ_GAP=1`)
  - `UDP_RMS_P50=0.000349`, `UDP_RMS_P90=0.119259`
  - `UDP_CLIP_RATIO=0.00000000`
  - Transcript: `"I bought a new set of 2D X-ray LTS-1..."` (repeated)
  - Phrase fidelity score vs expected prompt text: `0.0000`
- Loud run:
  - `UDP_PACKETS=562`
  - `UDP_SEQ_GAPS=1`
  - `UDP_RMS_P50=0.000225`, `UDP_RMS_P90=0.043642`
  - Transcript empty, fidelity `0.0000`

## Observed Failure / Quality Characteristics

1. **Silence and speech are distinguishable in upper-percentile energy, but median energy remains near floor.**
2. **Noise gate is activating for most chunks even during speech runs** (`~69%` to `~90%` gate-active), indicating sparse/fragmented voiced capture at ~2 ft.
3. **No sustained clipping observed** (`clip_ratio=0` in all trials).
4. **UDP stream remains active**, with minor packet gaps (low-level transport degradation, not path failure).
5. **Final transcript fidelity is poor under live-room conditions** with promoted values (incorrect/empty final transcriptions in measured runs).
6. **Active Pi production file still uses baseline values** (`0.0005/0.08/28.0`), while promoted values were only tested via temporary runtime override.

## Defect Classification

| ID | Defect | Classification | Severity | Cause Proven |
|---|---|---|---|---|
| D1 | Live transcript fidelity failure at ~2 ft with promoted calibration | **Verified** | High | No |
| D2 | Speech capture heavily gated at ~2 ft under promoted calibration | **Verified** | Medium | Partially |
| D3 | Minor UDP packet continuity loss | **Verified** | Low | No |
| D4 | Active Pi runtime config drift from promoted calibration artifacts | **Verified** | Medium | Yes |
| D5 | Front-end hardware/environment contribution (distance/SNR/mechanical noise) | **Suspected** | Medium | No |
| D6 | Segmentation threshold interplay with gated chunk distribution | **Unresolved** | Medium | No |

## Problem Type Determination

- **Configuration:** Yes (runtime config drift is verified).
- **Calibration:** Yes (promoted values did not achieve required live transcript fidelity).
- **Hardware handling:** Suspected contributor.
- **Transport:** Minor contributor (low-level loss/jitter only).
- **Speech segmentation:** Likely contributor; mechanism not yet proven.
- **Overall:** Combination (calibration + segmentation + possible front-end handling).

## Recommended Calibration Outcomes (Evidence-Based)

### Validated outcomes from this live follow-up

- `NOISE_GATE_RMS=0.003`, `TARGET_RMS=0.070`, `MAX_GAIN=20.0` **did not validate final transcript fidelity** at ~2 ft in this room.
- Clipping risk remains low with these values (positive finding).

### Experimental candidates (not validated as corrective)

- Re-open controlled sweep around lower gate aggressiveness and segmentation interaction:
  - `NOISE_GATE_RMS`: test `0.0012`, `0.0018`, `0.0024`
  - `TARGET_RMS`: test `0.060`, `0.070`
  - `MAX_GAIN`: test `18`, `22`
  - Coupled PC segmentation checks: `volume_threshold` and effective threshold behavior vs measured `proc_rms` distribution

## Validation Requirement Check

| Requirement | Result | Evidence |
|---|---|---|
| Silence and speech distinguishable by measured levels | **Pass (degraded)** | p90 speech > p90 silence, but p50 remains near floor |
| Normal speech at ~2 ft captured without sustained clipping | **Pass** | clip ratios remained zero |
| UDP stream remains active during testing | **Pass** | packet flow present in all UDP runs, with minor gaps |
| Recommended threshold/AGC values derived from measurements | **Pass** | all recommendations tied to measured RMS/gate/gain/transcript results |

## Temporary Changes

- Temporary in-process overrides were used on Pi during diagnostics:
  - `NOISE_GATE_RMS=0.003`
  - `TARGET_RMS=0.070`
  - `MAX_GAIN=20.0`
- No production files were modified on Pi or in repository.
- Temporary overrides ended when diagnostic processes exited.

## Routing Gate (Explicit Answers)

1. **Was a defect verified?**  
   **Yes.** Transcript fidelity failure and over-gating at ~2 ft were verified.

2. **Was the exact failure mechanism proven?**  
   **No.** Multiple contributors remain plausible (gate/AGC calibration interaction, segmentation thresholds, hardware/environment SNR).

3. **Is there direct evidence that a specific production change will correct it?**  
   **No.** Current live evidence does not prove a single corrective production change.

4. **Were proposed calibration values validated through controlled repeated trials?**  
   **No.** Previously promoted values did not pass live transcript fidelity validation here.

## Recommended Next Agent

**Root Cause Analysis Agent**

## Recommended Next Objective

Prove the exact failure mechanism for live-room transcript failure at ~2 ft by isolating:
1) Pi-side capture SNR and gate/AGC interaction,  
2) PC-side segmentation threshold dynamics against real `proc_rms` distributions, and  
3) whether hardware handling/noise floor is dominating speech energy at current microphone placement.

## Checkpoint Recommendation

**Continue Investigation** (no implementation recommendation yet).

## Suggested `project_state.json` updates for Documentation Steward (do not apply in this task)

- Keep `AUDIO-001` open.
- Mark live follow-up with promoted values as failed transcript-fidelity validation.
- Set next recommended agent to `Root Cause Analysis Agent`.
