initially the project was broken with a few workable parts. so we started like this
Validation / Diagnostic Agent
        ↓
Runtime Implementation Agent.
        ↓
Pi Audio Diagnostic Agent
        ↓
Validation / Test Agent
        ↓
Runtime Implementation Agent
        ↓
Validation / Test Agent
        ↓
Stable Commit to Project

Now that we are stable and there are only a couple concerns we will 
perferm RCA between validation and implementation.

        ↓
Root Cause Analysis   ← new step
        ↓
Implementation - Runtime Reliability Agent
        ↓
Validation - very similar to final valiation of first push, just need to add validation of the reliability agents work
        ↓               an issue was identified of severity medium. RCA that bitch.
Root Cause Analysis - issue identified in e2e_runtime_validation_post_hardening_2026-06-26
        ↓
Implementation - Runtime Reliability Agent - address issue in ssh_false_negative_reliability_fix_2026-06-2
