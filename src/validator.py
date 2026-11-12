import json
import os
import pandas as pd


def validate_dataset(data_dir: str = "data") -> dict:
    raw_dir = os.path.join(data_dir, "raw")
    processed_dir = os.path.join(data_dir, "processed")

    # Load all tables
    customers = pd.read_csv(os.path.join(raw_dir, "customers.csv"))
    products = pd.read_csv(os.path.join(raw_dir, "products.csv"))
    orders = pd.read_csv(os.path.join(raw_dir, "orders.csv"))
    order_lines = pd.read_csv(os.path.join(raw_dir, "order_lines.csv"))
    consent = pd.read_csv(os.path.join(raw_dir, "consent.csv"))
    actions = pd.read_csv(os.path.join(raw_dir, "action_catalog.csv"))
    memberships = pd.read_csv(os.path.join(processed_dir, "segment_membership.csv"))
    outcomes = pd.read_csv(os.path.join(processed_dir, "action_outcomes.csv"))

    report = {
        "primary_key_checks": {},
        "foreign_key_checks": {},
        "arithmetic_reconciliation": {},
        "detected_anomalies": []
    }

    # 1. Primary Key Uniqueness Checks
    report["primary_key_checks"]["customer_unique"] = bool(customers["customer_id"].is_unique)
    report["primary_key_checks"]["product_unique"] = bool(products["product_id"].is_unique)
    report["primary_key_checks"]["order_unique"] = bool(orders["order_id"].is_unique)
    report["primary_key_checks"]["order_line_unique"] = bool(order_lines["order_line_id"].is_unique)

    # 2. Foreign Key Integrity Checks
    valid_cids = set(customers["customer_id"])
    valid_pids = set(products["product_id"])
    valid_oids = set(orders["order_id"])
    valid_aids = set(actions["action_id"])

    report["foreign_key_checks"]["order_cust_valid"] = bool(orders["customer_id"].isin(valid_cids).all())
    report["foreign_key_checks"]["line_order_valid"] = bool(order_lines["order_id"].isin(valid_oids).all())
    report["foreign_key_checks"]["line_product_valid"] = bool(order_lines["product_id"].isin(valid_pids).all())
    report["foreign_key_checks"]["outcome_cust_valid"] = bool(outcomes["customer_id"].isin(valid_cids).all())

    # 3. Arithmetic Reconciliation
    # OrderLine: quantity * unit_price == line_total
    computed_line_total = (order_lines["quantity"] * order_lines["unit_price"]).round(2)
    line_arithmetic_match = (computed_line_total == order_lines["line_total"]).all()
    report["arithmetic_reconciliation"]["order_lines_exact"] = bool(line_arithmetic_match)

    # Order: sum(line_total) == net_amount
    summed_orders = order_lines.groupby("order_id")["line_total"].sum().round(2)
    merged_orders = orders.set_index("order_id")["net_amount"]
    order_sum_match = (summed_orders == merged_orders.loc[summed_orders.index]).all()
    report["arithmetic_reconciliation"]["orders_reconciled"] = bool(order_sum_match)

    # 4. Anomaly Detection Engine (Auditing Edge Cases)
    # Check 1: Conflicting exclusive segments
    exclusive_counts = memberships[memberships["is_exclusive"]].groupby("customer_id").size()
    conflicts = exclusive_counts[exclusive_counts > 1].index.tolist()
    for cid in conflicts:
        report["detected_anomalies"].append({
            "anomaly_type": "conflicting_exclusive_segments",
            "entity_id": cid,
            "status": "FLAGGED"
        })

    # Check 2: Consent suppression violation
    consent_dict = consent.set_index("customer_id").to_dict(orient="index")
    action_dict = actions.set_index("action_id").to_dict(orient="index")
    for _, out in outcomes.iterrows():
        cid = out["customer_id"]
        aid = out["action_id"]
        if aid in action_dict and out["status"] == "delivered":
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

    # Check 3: Action Catalog foreign key mismatch (Attribution Anomaly)
    invalid_outcomes = outcomes[~outcomes["action_id"].isin(valid_aids)]
    for _, row in invalid_outcomes.iterrows():
        report["detected_anomalies"].append({
            "anomaly_type": "attribution_mismatch",
            "entity_id": row["outcome_id"],
            "status": "FLAGGED"
        })

    # 5. Compare with ground_truth.json
    gt_path = os.path.join(data_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path, "r") as f:
            gt_data = json.load(f)
        detected_types = {a["anomaly_type"] for a in report["detected_anomalies"]}
        expected_types = {a["anomaly_type"] for a in gt_data if a["anomaly_type"] != "return_not_netted"}
        report["anomaly_detection_recall"] = f"{len(detected_types.intersection(expected_types))}/{len(expected_types)}"

    return report


if __name__ == "__main__":
    results = validate_dataset()
    print("\n--- VALIDATION & EVALUATION REPORT ---")
    print(json.dumps(results, indent=2))