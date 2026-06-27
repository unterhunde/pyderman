# Report Standards

## Document Metadata

| Field                 | Value                                                                                                                           |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Title**             | Report Standards                                                                                                                |
| **Purpose**           | Define the required structure, content, and completion criteria for all engineering reports generated during PiBot development. |
| **Last Updated**      | 2026-06-26                                                                                                                      |
| **Related Documents** | Documentation_Standards.md, Prompt_Standards.md, Development_Lifecycle.md, Agent_Orchestration_Guide.md                         |

# Purpose

All engineering artifacts produced by AI agents shall conform to one of the report contracts defined in this document.

The purpose of these contracts is to:

* Standardize engineering documentation.
* Preserve project knowledge between agent sessions.
* Reduce prompt complexity.
* Provide consistent project history.
* Enable deterministic agent handoffs.
* Ensure engineering decisions are traceable.

Every report consists of:

* Required metadata
* Required sections
* Required completion criteria
* A standard template

# Universal Report Metadata

Every report shall begin with:

```text
Title
Purpose
Date
Author / Agent
Source Prompt
Related Documents
Related Implementation
Related Validation
Assumptions
```

<!-- copilot:ignore -->
Validation Report Template
<!-- copilot:unignore -->

# Validation Report

## Purpose

Documents the results of validation activities and determines whether the implementation is ready for checkpoint, additional implementation, or Root Cause Analysis.

## Required Sections

### Metadata

### Goal

Describe what was validated.

### Scope

List:

* Components
* Files
* Features
* Runtime paths

### Environment

Document:

* Hardware
* Software
* Configuration
* Test conditions

### Evidence

Reference:

* logs
* screenshots
* diagnostics
* implementation records
* validation artifacts

### Pass / Fail Matrix

| Test | Result | Notes |
| ---- | ------ | ----- |

### Observations

Unexpected behavior that is not necessarily a defect.

### Remaining Defects

Rank:

* Critical
* High
* Medium
* Low

### Regression Status

State whether previous fixes remain validated.

### Recommended Next Agent

Select exactly one.

Explain why.

### Recommended Next Prompt

Describe the objective of the next prompt.

Do **not** generate the prompt.

### Checkpoint Recommendation

Choose one:

* Commit
* Continue Implementation
* Continue Investigation
* Architecture Review Required

Provide justification.

## Validation Report Template

# Validation Report

## Metadata

## Goal

## Scope

## Environment

## Evidence

## Pass / Fail Matrix

## Observations

## Remaining Defects

## Regression Status

## Recommended Next Agent

## Recommended Next Prompt

## Checkpoint Recommendation

<!-- copilot:ignore -->
Root Cause Analysis Template
<!-- copilot:unignore -->

# Root Cause Analysis Report

## Purpose

Determine and document the verified cause of an observed defect.

## Required Sections

### Metadata

### Problem Statement

### Evidence Collected

### Timeline

### Failure Classification

### Root Cause

### Rejected Hypotheses

### Recommended Fix

### Recommended Validation

### Recommended Next Agent

## RCA Template

# Root Cause Analysis

## Metadata

## Problem Statement

## Evidence Collected

## Timeline

## Failure Classification

## Root Cause

## Rejected Hypotheses

## Recommended Fix

## Recommended Validation

## Recommended Next Agent

<!-- copilot:ignore -->
Implementation Record Template
<!-- copilot:unignore -->

# Implementation Record

## Purpose

Document implementation work performed during a development task.

## Required Sections

### Metadata

### Goal

### Files Modified

### Behavior Before

### Behavior After

### Design Decisions

Explain significant implementation decisions.

### Tests Added or Updated

### Validation Results

### Remaining Issues

### Recommended Next Agent

## Implementation Record Template

# Implementation Record

## Metadata

## Goal

## Files Modified

## Behavior Before

## Behavior After

## Design Decisions

## Tests Added or Updated

## Validation Results

## Remaining Issues

## Recommended Next Agent

<!-- copilot:ignore -->
Architecture Review Template
<!-- copilot:unignore -->

# Architecture Review

## Purpose

Evaluate whether the current architecture remains appropriate.

## Required Sections

* Metadata
* Review Scope
* Current Architecture
* Findings
* Risks
* Recommendations
* Approved Changes
* Recommended Next Agent

## Architecture Review Template

# Architecture Review

## Metadata

## Review Scope

## Current Architecture

## Findings

## Risks

## Recommendations

## Approved Changes

## Recommended Next Agent

<!-- copilot:ignore -->
Performance Report Template
<!-- copilot:unignore -->

# Performance Report

## Purpose

Measure runtime behavior and identify performance bottlenecks.

## Required Sections

* Metadata
* Goal
* Test Environment
* Metrics
* Results
* Bottlenecks
* Recommendations
* Recommended Next Agent

## Performance Report Template

# Performance Report

## Metadata

## Goal

## Test Environment

## Metrics

## Results

## Bottlenecks

## Recommendations

## Recommended Next Agent

<!-- copilot:ignore -->
Checkpoint Template
<!-- copilot:unignore -->

# Checkpoint Report

## Purpose

Capture the state of the project at a stable milestone.

## Required Sections

### Metadata

### Validated Capabilities

### Architecture Changes

### Reliability Improvements

### Technical Debt

### Known Limitations

### Remaining Work

### Recommended Next Development Phase

### Evidence

### Commit Recommendation

## Checkpoint Template

# Checkpoint Summary

## Metadata

## Validated Capabilities

## Architecture Changes

## Reliability Improvements

## Technical Debt

## Known Limitations

## Remaining Work

## Recommended Next Development Phase

## Evidence

## Commit Recommendation

# Completion Criteria

Every report shall:

* Reference supporting implementation, diagnostics, validation, or architecture documents.
* Record only verified observations.
* Clearly separate facts from recommendations.
* Recommend exactly one next agent whenever practical.
* Recommend the objective of the next task.
* Be stored in the appropriate engineering records directory.
* Preserve project history rather than overwrite it.

Reports are engineering records and shall remain immutable after completion except to correct factual inaccuracies or update cross-references.