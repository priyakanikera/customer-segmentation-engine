import hashlib
import json
import os
import pandas as pd


def file_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_dataset(data_dir: str = "data") -> dict:
    raw_dir = os.path.join(data_dir, "raw")
    processed_dir = os.path.join(data_dir, "processed")

    # Load all tables
    customers = pd.read_csv(os.path.join(raw_dir, "customers.csv"))
    products = pd.read_csv(os.path.join(raw_dir, "products.csv"))
    orders = pd.read_csv(os.path.join(raw_dir, "orders.csv"))
    order_lines = pd.read_csv(os.path.join(raw_dir, "order_lines.csv"))
    events = pd.read_csv(os.path.join(raw_dir, "engagement_events.csv"))
    support = pd.read_csv(os.path.join(raw_dir, "support_cases.csv"))
    consent = pd.read_csv(os.path.join(raw_dir, "consent.csv"))
    actions = pd.read_csv(os.path.join(raw_dir, "action_catalog.csv"))
    features = pd.read_csv(os.path.join(processed_dir, "customer_features.csv"))
    memberships = pd.read_csv(os.path.join(processed_dir, "segment_membership.csv"))
    outcomes = pd.read_csv(os.path.join(processed_dir, "action_outcomes.csv"))

    report = {
        "primary_key_and_duplicate_checks": {},
        "foreign_key_checks": {},
        "enum_checks": {},
        "date_ordering_checks": {},
        "arithmetic_reconciliation": {},
        "detected_anomalies": []
    }

    # 1. Primary Key Uniqueness & Full-Row Duplicate Checks
    report["primary_key_and_duplicate_checks"]["customer_pk_unique"] = bool(customers["customer_id"].is_unique)
    report["primary_key_and_duplicate_checks"]["product_pk_unique"] = bool(products["product_id"].is_unique)
    report["primary_key_and_duplicate_checks"]["order_pk_unique"] = bool(orders["order_id"].is_unique)
    report["primary_key_and_duplicate_checks"]["order_line_pk_unique"] = bool(order_lines["order_line_id"].is_unique)
    report["primary_key_and_duplicate_checks"]["event_pk_unique"] = bool(events["event_id"].is_unique)
    report["primary_key_and_duplicate_checks"]["no_duplicate_customers"] = bool(customers.duplicated().sum() == 0)
    report["primary_key_and_duplicate_checks"]["no_duplicate_orders"] = bool(orders.duplicated().sum() == 0)

    # 2. Foreign Key Integrity Checks
    valid_cids = set(customers["customer_id"])
    valid_pids = set(products["product_id"])
    valid_oids = set(orders["order_id"])
    valid_aids = set(actions["action_id"])

    report["foreign_key_checks"]["order_cust_valid"] = bool(orders["customer_id"].isin(valid_cids).all())
    report["foreign_key_checks"]["line_order_valid"] = bool(order_lines["order_id"].isin(valid_oids).all())
    report["foreign_key_checks"]["line_product_valid"] = bool(order_lines["product_id"].isin(valid_pids).all())
    report["foreign_key_checks"]["event_cust_valid"] = bool(events["customer_id"].isin(valid_cids).all())
    report["foreign_key_checks"]["support_cust_valid"] = bool(support["customer_id"].isin(valid_cids).all())
    report["foreign_key_checks"]["outcome_cust_valid"] = bool(outcomes["customer_id"].isin(valid_cids).all())

    # 3. Allowed Enum Validation
    report["enum_checks"]["lifecycle_valid"] = bool(customers["lifecycle_stage"].isin(["new", "active", "dormant", "churned"]).all())
    report["enum_checks"]["order_status_valid"] = bool(orders["order_status"].isin(["completed", "cancelled", "returned"]).all())
    report["enum_checks"]["event_channel_valid"] = bool(events["channel"].isin(["email_open", "web_visit", "app_login", "sms_click"]).all())
    report["enum_checks"]["outcome_status_valid"] = bool(outcomes["status"].isin(["delivered", "suppressed", "converted", "bounced"]).all())

    # 4. Chronological Date Ordering Checks
    cust_created = customers.set_index("customer_id")["created_at"]
    orders_with_cust = orders.join(cust_created, on="customer_id")
    report["date_ordering_checks"]["orders_after_customer_created"] = bool(
        (orders_with_cust["order_timestamp"] >= orders_with_cust["created_at"]).all()
    )

    events_with_cust = events.join(cust_created, on="customer_id")
    report["date_ordering_checks"]["events_after_customer_created"] = bool(
        (events_with_cust["event_timestamp"] >= events_with_cust["created_at"]).all()
    )

    resolved_cases = support[support["closed_at"].notna()]
    report["date_ordering_checks"]["support_closed_after_opened"] = bool(
        (resolved_cases["closed_at"] >= resolved_cases["opened_at"]).all()
    )

    # 5. Arithmetic Reconciliation
    computed_line_total = (order_lines["quantity"] * order_lines["unit_price"]).round(2)
    report["arithmetic_reconciliation"]["order_lines_exact"] = bool((computed_line_total == order_lines["line_total"]).all())

    summed_orders = order_lines.groupby("order_id")["line_total"].sum().round(2)
    merged_orders = orders.set_index("order_id")["net_amount"]
    report["arithmetic_reconciliation"]["orders_reconciled"] = bool(
        (summed_orders == merged_orders.loc[summed_orders.index]).all()
    )

    # 6. Anomaly Detection Engine (Auditing All 4 Edge Cases)
    # Anomaly 1: Conflicting exclusive segments
    exclusive_counts = memberships[memberships["is_exclusive"]].groupby("customer_id").size()
    for cid in exclusive_counts[exclusive_counts > 1].index.tolist():
        report["detected_anomalies"].append({
            "anomaly_type": "conflicting_exclusive_segments",
            "entity_id": cid,
            "status": "FLAGGED"
        })

    # Anomaly 2: Consent suppression violation
    consent_dict = consent.set_index("customer_id").to_dict(orient="index")
    action_dict = actions.set_index("action_id").to_dict(orient="index")
    delivered_outcomes = outcomes[outcomes["status"] == "delivered"]
    for _, out in delivered_outcomes.iterrows():
        cid = out["customer_id"]
        aid = out["action_id"]
        if aid in action_dict:
            chan = action_dict[aid]["target_channel"]
            c_info = consent_dict.get(cid, {})
            if (chan == "email" and not c_info.get("email_opt_in", False)) or \
               (chan == "sms" and not c_info.get("sms_opt_in", False)):
                report["detected_anomalies"].append({
                    "anomaly_type": "consent_suppression_violation",
                    "entity_id": cid,
                    "channel": chan,
                    "status": "FLAGGED"
                })

    # Anomaly 3: Return not netted from spend
    valid_orders = orders[orders["order_status"].isin(["completed", "returned"])].copy()
    valid_orders["expected_signed"] = valid_orders["net_amount"].where(
        valid_orders["order_status"] == "completed", -valid_orders["net_amount"]
    )
    expected_spend = valid_orders.groupby("customer_id")["expected_signed"].sum().round(2)
    actual_spend = features.set_index("customer_id")["net_spend"].round(2)
    aligned = actual_spend.reindex(expected_spend.index, fill_value=0.0)
    mismatched_spend_cids = expected_spend[expected_spend != aligned].index.tolist()
    for cid in mismatched_spend_cids:
        ret_ord = orders[(orders["customer_id"] == cid) & (orders["order_status"] == "returned")].iloc[0]["order_id"]
        report["detected_anomalies"].append({
            "anomaly_type": "return_not_netted",
            "entity_id": ret_ord,
            "customer_id": cid,
            "status": "FLAGGED"
        })

    # Anomaly 4: Attribution mismatch
    invalid_outcomes = outcomes[~outcomes["action_id"].isin(valid_aids)]
    for _, row in invalid_outcomes.iterrows():
        report["detected_anomalies"].append({
            "anomaly_type": "attribution_mismatch",
            "entity_id": row["outcome_id"],
            "status": "FLAGGED"
        })

    # 7. Compare against isolated ground_truth.json
    gt_path = os.path.join(data_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path, "r") as f:
            gt_data = json.load(f)
        detected_types = {a["anomaly_type"] for a in report["detected_anomalies"]}
        expected_types = {a["anomaly_type"] for a in gt_data}
        report["anomaly_detection_recall"] = f"{len(detected_types.intersection(expected_types))}/{len(expected_types)}"

    # Export Validation Summary & Source Manifest (Step 9 Requirement)
    with open(os.path.join(data_dir, "validation_summary.json"), "w") as f:
        json.dump(report, f, indent=2)

    manifest = {
        "provenance": "100% synthetic deterministic generation (no external third-party PII or restricted datasets)",
        "generator_command": "python3 run_pipeline.py --seed 20261022 --customers 50000 --orders 200000 --events 1000000",
        "fixed_seed": 20261022,
        "artifacts": {}
    }
    for folder in [raw_dir, processed_dir]:
        for fname in sorted(os.listdir(folder)):
            if fname.endswith(".csv"):
                fpath = os.path.join(folder, fname)
                df_tmp = pd.read_csv(fpath)
                manifest["artifacts"][f"{os.path.basename(folder)}/{fname}"] = {
                    "row_count": len(df_tmp),
                    "sha256": file_sha256(fpath)
                }

    with open(os.path.join(data_dir, "source_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    return report


if __name__ == "__main__":
    results = validate_dataset()
    print("\n--- VALIDATION & EVALUATION REPORT ---")
    print(json.dumps(results, indent=2))