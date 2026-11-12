# Enterprise Data Dictionary & Entity Relationship Specification

## 1. Overview & Nomenclature Standards
This specification details the schema, integrity constraints, and domain-specific validation rules for the Customer Segmentation & Next-Best-Action Engine[cite: 1, 5].

### ID & Formatting Conventions
- **Customer**: `CUS-000001` (zero-padded 6 digits)[cite: 5, 8]
- **Product**: `PRD-000001` (zero-padded 6 digits)
- **Order**: `ORD-2026-000001` (`ORD-<year>-<6 digits>`)[cite: 5, 8]
- **OrderLine**: `ORDL-2026-000001-01` (`ORDL-<year>-<order_seq>-<line_seq>`)
- **EngagementEvent**: `EVT-2026-000001` (`EVT-<year>-<6 digits>`)
- **SupportCase**: `CAS-2026-000001` (`CAS-<year>-<6 digits>`)
- **Consent**: `CNS-000001` (`CNS-<6 digits>`)
- **SegmentRule**: `SEG-2026-000001` (`SEG-<year>-<6 digits>`)[cite: 5, 8]
- **SegmentMembership**: `MEM-<segment-id>-<customer-id>` (e.g., `MEM-SEG-2026-000001-CUS-000001`)[cite: 5, 8]
- **ActionCatalog**: `ACTN-2026-000001` (`ACTN-<year>-<6 digits>`)[cite: 5, 8]
- **ActionOutcome**: `OUT-2026-000001` (`OUT-<year>-<6 digits>`)

---

## 2. Master & Parent Entities

### Entity: `Customer`
Represents the base demographic and account profile[cite: 2, 5].
- **Cardinality**: 1 to Many (`Order`, `EngagementEvent`, `SupportCase`, `SegmentMembership`, `ActionOutcome`), 1 to 1 (`Consent`)[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Primary Key | Immutable; referenced by all dependent events[cite: 5, 8]. |
| `first_name` | String | Yes | Non-empty text | N/A | Non-unique | Standard synthetic alphabetic string. |
| `last_name` | String | Yes | Non-empty text | N/A | Non-unique | Standard synthetic alphabetic string. |
| `email` | String | Yes | `^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$` | N/A | Unique | Pseudonymized email address. |
| `phone_number` | String | Yes | `^\+1-\d{3}-\d{3}-\d{4}$` | N/A | Unique | Deterministic synthetic phone number. |
| `created_at` | Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Base reference date; must precede all transactions[cite: 6]. |
| `lifecycle_stage` | Enum | Yes | `new`, `active`, `dormant`, `churned` | `new` | Non-unique | Derived state based on activity recency. |

---

### Entity: `Product`
Master product catalog containing hierarchical categorization and pricing[cite: 2, 5].
- **Cardinality**: 1 to Many (`OrderLine`)[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `product_id` | String | Yes | `^PRD-\d{6}$` | N/A | Primary Key | Immutable product identifier. |
| `sku` | String | Yes | `^[A-Z]{3}-\d{4}$` | N/A | Unique | Internal inventory stock keeping unit. |
| `product_name` | String | Yes | Non-empty text | N/A | Non-unique | Descriptive commercial item name. |
| `category` | Enum | Yes | `electronics`, `apparel`, `home`, `services` | N/A | Non-unique | Taxonomy domain classification[cite: 2, 5]. |
| `unit_price` | Decimal | Yes | `> 0.00` | USD ($) | Non-unique | Base unit cost; scale of 2 decimal places. |

---

### Entity: `Consent`
Tracks explicit opt-in permissions and regulatory contact preferences[cite: 2, 5].
- **Cardinality**: 1 to 1 with `Customer`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `consent_id` | String | Yes | `^CNS-\d{6}$` | N/A | Primary Key | Unique consent ledger identifier. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference a valid `Customer.customer_id`[cite: 2, 8]. |
| `email_opt_in` | Boolean | Yes | `True`, `False` | `False` | Non-unique | If `False`, blocks all email marketing actions[cite: 2, 7]. |
| `sms_opt_in` | Boolean | Yes | `True`, `False` | `False` | Non-unique | If `False`, blocks all SMS outreach actions[cite: 2, 7]. |
| `updated_at` | Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | History must be persisted without overwriting[cite: 2]. |

---

## 3. Transactional & Event Entities

### Entity: `Order`
Financial purchase transaction headers[cite: 1, 5].
- **Cardinality**: Many to 1 with `Customer`, 1 to Many with `OrderLine`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_id` | String | Yes | `^ORD-2026-\d{6}$` | N/A | Primary Key | Unique order identifier[cite: 5, 8]. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference valid `Customer.customer_id`[cite: 2, 8]. |
| `order_timestamp`| Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Must be $\ge Customer.created\_at$[cite: 6]. |
| `order_status` | Enum | Yes | `completed`, `cancelled`, `returned` | `completed` | Non-unique | Drives revenue recognition[cite: 6, 7]. |
| `net_amount` | Decimal | Yes | Real numbers | USD ($) | Non-unique | Must equal $\sum(\text{OrderLine.line\_total})$[cite: 6]. |

---

### Entity: `OrderLine`
Granular line-item breakdown of individual products within an order[cite: 2, 5].
- **Cardinality**: Many to 1 with `Order`, Many to 1 with `Product`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `order_line_id`| String | Yes | `^ORDL-2026-\d{6}-\d{2}$` | N/A | Primary Key | Composite key with 2-digit line counter. |
| `order_id` | String | Yes | `^ORD-2026-\d{6}$` | N/A | Foreign Key | Must reference valid `Order.order_id`[cite: 2, 8]. |
| `product_id` | String | Yes | `^PRD-\d{6}$` | N/A | Foreign Key | Must reference valid `Product.product_id`[cite: 2, 8]. |
| `quantity` | Integer | Yes | $\ge 1$ | Units | Non-unique | Number of product units purchased. |
| `unit_price` | Decimal | Yes | `> 0.00` | USD ($) | Non-unique | Replicated from `Product.unit_price` at purchase time. |
| `line_total` | Decimal | Yes | `> 0.00` | USD ($) | Non-unique | Exact calculated reconciliation: `quantity * unit_price`[cite: 6]. |

---

### Entity: `EngagementEvent`
Behavioral interaction telemetry across multi-channel touchpoints[cite: 1, 5].
- **Cardinality**: Many to 1 with `Customer`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `event_id` | String | Yes | `^EVT-2026-\d{6}$` | N/A | Primary Key | Unique engagement event identifier. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference valid `Customer.customer_id`[cite: 2, 8]. |
| `event_timestamp`| Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Must be chronological and $\ge Customer.created\_at$[cite: 6]. |
| `channel` | Enum | Yes | `email_open`, `web_visit`, `app_login`, `sms_click` | N/A | Non-unique | Touchpoint channel medium[cite: 5]. |
| `device` | Enum | Yes | `mobile`, `desktop`, `tablet` | N/A | Non-unique | Client user agent device classification. |

---

### Entity: `SupportCase`
Customer service tickets, complaints, and resolution tracking[cite: 5, 8].
- **Cardinality**: Many to 1 with `Customer`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `case_id` | String | Yes | `^CAS-2026-\d{6}$` | N/A | Primary Key | Unique support case ticket identifier. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference valid `Customer.customer_id`[cite: 2, 8]. |
| `opened_at` | Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Case open timestamp[cite: 8]. |
| `closed_at` | Timestamp | No | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) or null | N/A | Non-unique | Must be $\ge opened\_at$; null if unresolved[cite: 6]. |
| `status` | Enum | Yes | `open`, `escalated`, `resolved` | `open` | Non-unique | Case lifecycle state[cite: 8]. |
| `cost_to_serve`| Decimal | Yes | $\ge 0.00$ | USD ($) | Non-unique | Aggregated support overhead; triggers high-cost flag[cite: 7]. |

---

## 4. Segmentation & Recommendation Entities

### Entity: `SegmentRule`
Declarative criteria defining behavioral, RFM, or demographic cohorts[cite: 2, 5].
- **Cardinality**: 1 to Many with `SegmentMembership`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `segment_id` | String | Yes | `^SEG-2026-\d{6}$` | N/A | Primary Key | Unique segment rule identifier[cite: 5, 8]. |
| `segment_name` | String | Yes | Non-empty text | N/A | Unique | Human-readable label (e.g., `VIP High Spender`, `Churn Risk`)[cite: 1, 5]. |
| `rule_criteria`| JSON | Yes | Valid JSON logic string | N/A | Non-unique | Transparent query/filter condition logic[cite: 1, 2]. |
| `is_exclusive` | Boolean | Yes | `True`, `False` | `False` | Non-unique | Flags mutually exclusive cohorts (e.g., `VIP` vs `Dormant`)[cite: 6, 7]. |

---

### Entity: `SegmentMembership`
Bridge table capturing customer assignment to segments with audit timestamps[cite: 5, 8].
- **Cardinality**: Many to 1 with `Customer`, Many to 1 with `SegmentRule`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `membership_id`| String | Yes | `^MEM-SEG-\d{4}-\d{6}-CUS-\d{6}$` | N/A | Primary Key | Composite deterministic pattern: `MEM-<seg_id>-<cust_id>`[cite: 5, 8]. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference valid `Customer.customer_id`[cite: 2, 8]. |
| `segment_id` | String | Yes | `^SEG-2026-\d{6}$` | N/A | Foreign Key | Must reference valid `SegmentRule.segment_id`[cite: 2, 8]. |
| `assigned_at` | Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Audit timestamp of evaluation[cite: 1, 8]. |

---

### Entity: `ActionCatalog`
Pre-approved interventions, marketing offers, or retention plays[cite: 5, 8].
- **Cardinality**: 1 to Many with `ActionOutcome`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `action_id` | String | Yes | `^ACTN-2026-\d{6}$` | N/A | Primary Key | Unique action catalog identifier[cite: 5, 8]. |
| `action_name` | String | Yes | Non-empty text | N/A | Unique | Descriptive action name (e.g., `Winback 20% Off`)[cite: 1, 5]. |
| `target_channel`| Enum | Yes | `email`, `sms`, `in_app`, `support_call` | N/A | Non-unique | Must be validated against `Consent` flags[cite: 2, 7]. |
| `target_segment`| String | Yes | `^SEG-2026-\d{6}$` | N/A | Foreign Key | Default segment cohort targeted by this action[cite: 8]. |

---

### Entity: `ActionOutcome`
Audit trail of recommended actions executed or suppressed, along with subsequent conversion[cite: 1, 2, 5].
- **Cardinality**: Many to 1 with `Customer`, Many to 1 with `ActionCatalog`[cite: 8].

| Field Name | Type | Required | Allowed Values / Format | Units / Default | Uniqueness | Validation & Integrity Rule |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `outcome_id` | String | Yes | `^OUT-2026-\d{6}$` | N/A | Primary Key | Unique execution outcome identifier. |
| `action_id` | String | Yes | `^ACTN-2026-\d{6}$` | N/A | Foreign Key | Must reference valid `ActionCatalog.action_id`[cite: 2, 8]. |
| `customer_id` | String | Yes | `^CUS-\d{6}$` | N/A | Foreign Key | Must reference valid `Customer.customer_id`[cite: 2, 8]. |
| `status` | Enum | Yes | `delivered`, `suppressed`, `converted`, `bounced` | N/A | Non-unique | `suppressed` if consent opt-in is False[cite: 1, 7]. |
| `suppression_reason`| Enum / Null | No | `consent_withdrawn`, `high_service_cost`, `none` | `none` | Non-unique | Explicit explanation for suppression decisions[cite: 1, 2, 7]. |
| `executed_at` | Timestamp | Yes | ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ`) | N/A | Non-unique | Execution audit timestamp[cite: 1, 2]. |

---

## 5. Explicit Anomaly & Edge-Case Taxonomy
The synthetic engine injects known labeled anomalies tracked separately in `ground_truth.json` for validation[cite: 6, 8]:
1. **Conflicting Exclusive Segments**: A customer assigned concurrently to mutually exclusive segments (e.g., `VIP High-Spender` and `Dormant At-Risk`)[cite: 6, 7].
2. **Consent Suppression Violation**: An action routed through a channel where the customer has explicitly set opt-in to `False`[cite: 6, 7].
3. **Un-netted Return Spend**: An order marked as `returned` where order totals were not subtracted from cumulative customer spend[cite: 6, 7].
4. **Mismatched Attribution**: An `ActionOutcome` record attributed to an action that was never triggered or sent to that customer[cite: 6, 7].