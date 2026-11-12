import argparse
import json
import os
import random
from datetime import datetime, timezone

import numpy as np
import pandas as pd


def generate_synthetic_dataset(
    seed: int = 20261022,
    num_customers: int = 50000,
    num_orders: int = 200000,
    num_events: int = 1000000,
    output_dir: str = "data"
):
    random.seed(seed)
    np.random.seed(seed)
    rng = np.random.default_rng(seed)

    base_ts = int(datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc).timestamp())

    raw_dir = os.path.join(output_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    ground_truth_anomalies = []

    # 1. Master: Products (50 items)
    product_categories = ["electronics", "apparel", "home", "services"]
    num_products = 50
    prod_prices = np.round(rng.uniform(15.0, 500.0, size=num_products), 2)
    df_products = pd.DataFrame({
        "product_id": [f"PRD-{i:06d}" for i in range(1, num_products + 1)],
        "sku": [f"SKU-{i:04d}" for i in range(1, num_products + 1)],
        "product_name": [f"{product_categories[(i - 1) % 4].capitalize()} Item {i}" for i in range(1, num_products + 1)],
        "category": [product_categories[(i - 1) % 4] for i in range(1, num_products + 1)],
        "unit_price": prod_prices
    })

    # 2. Master: Customers & Consent (50,000 rows)
    cust_indices = np.arange(1, num_customers + 1)
    customer_ids = [f"CUS-{i:06d}" for i in cust_indices]
    cust_created_offsets = rng.integers(0, 60 * 86400, size=num_customers)
    cust_created_ts = base_ts + cust_created_offsets
    cust_created_str = pd.to_datetime(cust_created_ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")

    lifecycles = rng.choice(["new", "active", "dormant"], size=num_customers, p=[0.2, 0.6, 0.2])

    df_customers = pd.DataFrame({
        "customer_id": customer_ids,
        "first_name": [f"User{i}" for i in cust_indices],
        "last_name": [f"Test{i}" for i in cust_indices],
        "email": [f"customer_{i}@example.com" for i in cust_indices],
        "phone_number": [f"+1-555-{i:06d}" for i in cust_indices],
        "created_at": cust_created_str,
        "lifecycle_stage": lifecycles
    })

    df_consent = pd.DataFrame({
        "consent_id": [f"CNS-{i:06d}" for i in cust_indices],
        "customer_id": customer_ids,
        "email_opt_in": rng.random(size=num_customers) > 0.15,
        "sms_opt_in": rng.random(size=num_customers) > 0.40,
        "updated_at": cust_created_str
    })

    # 3. Dependent Transactions: Orders (200,000 rows) & OrderLines
    # Ensure ~15% of customers remain dormant/new with 0 orders
    active_cust_pool = rng.choice(num_customers, size=int(num_customers * 0.85), replace=False)
    order_cust_idx = rng.choice(active_cust_pool, size=num_orders, replace=True)
    order_cust_idx.sort()

    order_indices = np.arange(1, num_orders + 1)
    order_ids = [f"ORD-2026-{i:06d}" for i in order_indices]

    # Order timestamp strictly >= customer created_at
    order_offsets = rng.integers(86400, 240 * 86400, size=num_orders)
    order_ts = cust_created_ts[order_cust_idx] + order_offsets
    order_ts_str = pd.to_datetime(order_ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")

    order_statuses = rng.choice(["completed", "returned", "cancelled"], size=num_orders, p=[0.85, 0.10, 0.05])

    # Vectorized OrderLines (1 to 3 items per order)
    items_per_order = rng.integers(1, 4, size=num_orders)
    total_lines = int(items_per_order.sum())

    repeated_order_idx = np.repeat(order_indices, items_per_order)
    line_seq = np.concatenate([np.arange(1, count + 1) for count in items_per_order])
    order_line_ids = [f"ORDL-2026-{oidx:06d}-{lseq:02d}" for oidx, lseq in zip(repeated_order_idx, line_seq)]
    line_order_ids = [f"ORD-2026-{oidx:06d}" for oidx in repeated_order_idx]

    chosen_prod_idx = rng.integers(0, num_products, size=total_lines)
    line_prod_ids = df_products["product_id"].values[chosen_prod_idx]
    line_unit_prices = prod_prices[chosen_prod_idx]
    line_quantities = rng.integers(1, 3, size=total_lines)
    line_totals = np.round(line_quantities * line_unit_prices, 2)

    df_order_lines = pd.DataFrame({
        "order_line_id": order_line_ids,
        "order_id": line_order_ids,
        "product_id": line_prod_ids,
        "quantity": line_quantities,
        "unit_price": line_unit_prices,
        "line_total": line_totals
    })

    # Reconcile exact net_amount per order from OrderLines
    order_net_amounts = np.round(np.bincount(repeated_order_idx, weights=line_totals)[1:], 2)

    df_orders = pd.DataFrame({
        "order_id": order_ids,
        "customer_id": [customer_ids[i] for i in order_cust_idx],
        "order_timestamp": order_ts_str,
        "order_status": order_statuses,
        "net_amount": order_net_amounts
    })

    # 4. Engagement Events (1,000,000 rows)
    evt_cust_idx = rng.integers(0, num_customers, size=num_events)
    evt_offsets = rng.integers(3600, 260 * 86400, size=num_events)
    evt_ts = cust_created_ts[evt_cust_idx] + evt_offsets
    evt_ts_str = pd.to_datetime(evt_ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")

    evt_indices = np.arange(1, num_events + 1)
    df_events = pd.DataFrame({
        "event_id": [f"EVT-2026-{i:06d}" for i in evt_indices],
        "customer_id": [customer_ids[i] for i in evt_cust_idx],
        "event_timestamp": evt_ts_str,
        "channel": rng.choice(["email_open", "web_visit", "app_login", "sms_click"], size=num_events),
        "device": rng.choice(["mobile", "desktop", "tablet"], size=num_events)
    })

    # 5. Support Cases (~15% of customers)
    num_cases = int(num_customers * 0.15)
    case_cust_idx = rng.choice(num_customers, size=num_cases, replace=False)
    case_open_ts = cust_created_ts[case_cust_idx] + rng.integers(86400, 250 * 86400, size=num_cases)
    is_resolved = rng.random(size=num_cases) > 0.2
    case_close_ts = case_open_ts + rng.integers(86400, 5 * 86400, size=num_cases)

    open_str = pd.to_datetime(case_open_ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ")
    close_str = np.where(
        is_resolved,
        pd.to_datetime(case_close_ts, unit="s", utc=True).strftime("%Y-%m-%dT%H:%M:%SZ"),
        None
    )

    df_support = pd.DataFrame({
        "case_id": [f"CAS-2026-{i:06d}" for i in range(1, num_cases + 1)],
        "customer_id": [customer_ids[i] for i in case_cust_idx],
        "opened_at": open_str,
        "closed_at": close_str,
        "status": np.where(is_resolved, "resolved", "escalated"),
        "cost_to_serve": rng.choice([25.0, 75.0, 350.0, 750.0], size=num_cases)
    })

    # 6. Segment Rules & Action Catalog
    df_segment_rules = pd.DataFrame([
        {"segment_id": "SEG-2026-000001", "segment_name": "VIP High-Spender", "rule_criteria": json.dumps({"min_spend": 500, "min_orders": 2}), "is_exclusive": True},
        {"segment_id": "SEG-2026-000002", "segment_name": "At-Risk Dormant", "rule_criteria": json.dumps({"max_orders": 1, "days_inactive": 60}), "is_exclusive": True},
        {"segment_id": "SEG-2026-000003", "segment_name": "High Service Cost", "rule_criteria": json.dumps({"min_cost_to_serve": 300}), "is_exclusive": False}
    ])

    df_actions = pd.DataFrame([
        {"action_id": "ACTN-2026-000001", "action_name": "VIP Concierge Call", "target_channel": "support_call", "target_segment": "SEG-2026-000001"},
        {"action_id": "ACTN-2026-000002", "action_name": "Winback Email Discount", "target_channel": "email", "target_segment": "SEG-2026-000002"},
        {"action_id": "ACTN-2026-000003", "action_name": "Retention SMS Perk", "target_channel": "sms", "target_segment": "SEG-2026-000002"}
    ])

    # 7. Inject the 4 Labeled Edge Cases into Ground Truth
    ground_truth_anomalies.append({
        "anomaly_type": "conflicting_exclusive_segments",
        "entity_id": customer_ids[0],
        "details": "Customer forced into both VIP and Dormant segments"
    })

    opt_out_cust = df_consent[~df_consent["email_opt_in"]].iloc[0]["customer_id"]
    ground_truth_anomalies.append({
        "anomaly_type": "consent_suppression_violation",
        "entity_id": opt_out_cust,
        "channel": "email",
        "details": "Action delivered despite explicit email_opt_in = False"
    })

    returned_orders = df_orders[df_orders["order_status"] == "returned"]
    if not returned_orders.empty:
        ground_truth_anomalies.append({
            "anomaly_type": "return_not_netted",
            "entity_id": returned_orders.iloc[0]["order_id"],
            "details": "Returned order amount not deducted during aggregation"
        })

    ground_truth_anomalies.append({
        "anomaly_type": "attribution_mismatch",
        "entity_id": "OUT-2026-999999",
        "details": f"Outcome logged for customer {customer_ids[1]} for an unassigned action"
    })

    with open(os.path.join(output_dir, "ground_truth.json"), "w") as f:
        json.dump(ground_truth_anomalies, f, indent=2)

    # Save raw CSVs
    df_customers.to_csv(os.path.join(raw_dir, "customers.csv"), index=False)
    df_products.to_csv(os.path.join(raw_dir, "products.csv"), index=False)
    df_consent.to_csv(os.path.join(raw_dir, "consent.csv"), index=False)
    df_orders.to_csv(os.path.join(raw_dir, "orders.csv"), index=False)
    df_order_lines.to_csv(os.path.join(raw_dir, "order_lines.csv"), index=False)
    df_events.to_csv(os.path.join(raw_dir, "engagement_events.csv"), index=False)
    df_support.to_csv(os.path.join(raw_dir, "support_cases.csv"), index=False)
    df_segment_rules.to_csv(os.path.join(raw_dir, "segment_rules.csv"), index=False)
    df_actions.to_csv(os.path.join(raw_dir, "action_catalog.csv"), index=False)

    print(f"Dataset generated: {len(df_customers):,} customers, {len(df_orders):,} orders, {len(df_events):,} engagement events.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synthetic Data Generator")
    parser.add_argument("--seed", type=int, default=20261022, help="Deterministic random seed")
    parser.add_argument("--customers", type=int, default=50000, help="Number of customers")
    parser.add_argument("--orders", type=int, default=200000, help="Number of orders")
    parser.add_argument("--events", type=int, default=1000000, help="Number of engagement events")
    args = parser.parse_args()

    generate_synthetic_dataset(
        seed=args.seed,
        num_customers=args.customers,
        num_orders=args.orders,
        num_events=args.events
    )