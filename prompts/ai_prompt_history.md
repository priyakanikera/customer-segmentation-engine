# AI Collaboration & Prompt History Log

This document discloses how generative AI was utilized in designing, scaffolding, and reviewing this project in compliance with the candidate submission guidelines.

## 1. Scope of AI Assistance
- **Architecture & Schema Design**: Scaffolded the initial entity-relationship tables and data dictionary based on domain modeling principles.
- **Boilerplate Generation**: Accelerated creation of deterministic ID formatting, synthetic distribution routines, and Pytest test fixtures.
- **Audit Rule Design**: Structured edge-case scenarios and cross-table validation routines.

## 2. Personal Human Review & Modifications
- **Arithmetic Integrity**: Manually reviewed and corrected order line reconciliation and net spend calculation logic to ensure returned orders are subtracted from cumulative spend rather than simply omitted.
- **Suppression Logic**: Enforced strict suppression precedence where regulatory consent opt-outs immediately override any segment-based eligibility.
- **Validation Assertions**: Implemented automated checks comparing detected edge cases against an uncorrupted, isolated `ground_truth.json` file to prevent data leakage into input features.

## 3. High-Level Prompt Log
1. *Prompt*: "Help me design an enterprise customer segmentation schema covering 10 entities with deterministic ID nomenclature and explicit validation rules."
   - *Outcome*: Drafted data dictionary specifications and field constraints.
2. *Prompt*: "Generate a reproducible Python dataset script with fixed seeds and explicit injected edge cases (consent suppression violation, exclusive segment conflict, un-netted returns)."
   - *Outcome*: Created `src/generator.py` with parameterizable scale and isolated ground-truth generation.
3. *Prompt*: "Create a validator script that checks primary/foreign key integrity, arithmetic totals, and detects injected anomalies."
   - *Outcome*: Produced `src/validator.py` and unit tests in `tests/test_pipeline.py`.