# Customer Segmentation & Next-Best-Action Engine

An end-to-end, reproducible data pipeline designed to generate synthetic customer transactions, compute RFM and rule-based cohorts, recommend next-best actions with consent suppression, and audit data integrity against ground-truth anomalies.

---

## Architecture & Workflow

1. **Synthetic Generation (`src/generator.py`)**:
   - Master data (Customers, Products, Consent) is generated first, followed by dependent transaction/event records (Orders, OrderLines, Engagement, Support).
   - Zero-padded deterministic IDs (`CUS-000001`, `ORD-2026-000001`, `MEM-...`).
   - Generates an isolated `ground_truth.json` containing labeled edge cases without leaking into input features.
2. **Segmentation Engine (`src/segmenter.py`)**:
   - Reconciles net spend (`completed` - `returned`).
   - Calculates RFM metrics and service costs.
   - Evaluates rule criteria for cohorts (`VIP High-Spender`, `At-Risk Dormant`, `High Service Cost`).
3. **Recommendation Engine (`src/recommender.py`)**:
   - Matches segment memberships to actionable plays in `ActionCatalog`.
   - Enforces channel suppression when customer consent is withdrawn (`email_opt_in = False`, `sms_opt_in = False`) or service overhead is excessive.
4. **Validation Suite (`src/validator.py`)**:
   - Enforces primary key uniqueness, foreign key validity, and line item arithmetic reconciliation.
   - Audits outputs against injected edge cases and reports detection recall.

---

## Setup & Execution

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone <YOUR_PUBLIC_REPO_URL>
cd customer-segmentation-engine
pip install -r requirements.txt