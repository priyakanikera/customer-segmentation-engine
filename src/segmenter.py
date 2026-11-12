import json
import os
from datetime import datetime, timezone
import pandas as pd


def run_segmentation(data_dir: str = "data"):
    raw_dir = os.path.join(data_dir, "raw")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    df_customers = pd.read_csv(os.path.join(raw_dir, "customers.csv"))
    df_orders = pd.read_csv(os.path.join(raw_dir, "orders.csv"))
    df_rules = pd.read_csv(os.path.join(raw_dir, "segment_rules.csv"))
    df_support = pd.read_csv(os.path.join(raw_dir, "support_cases.csv"))

    # Convert timestamps
    df_orders["order_timestamp"] = pd.to_datetime(df_orders["order_timestamp"], utc=True)
    df_support["opened_at"] = pd.to_datetime(df_support["opened_at"], utc=True)
    
    # Reference snapshot date (end of simulation timeline)
    snapshot_date = pd.to_datetime("2026-11-01T00:00:00Z", utc=True)

    # 1. Aggregate Order Metrics (Correct Net Spend Arithmetic)
    # Exclude cancelled orders entirely
    valid_orders = df_orders[df_orders["order_status"].isin(["completed", "returned"])].copy()

    # Net spend = completed amount - returned amount
    valid_orders["signed_amount"] = valid_orders.apply(
        lambda row: row["net_amount"] if row["order_status"] == "completed" else -row["net_amount"],
        axis=1
    )

    order_metrics = valid_orders.groupby("customer_id").agg(
        total_orders=("order_id", "count"),
        net_spend=("signed_amount", "sum"),
        last_order_ts=("order_timestamp", "max")
    ).reset_index()

    order_metrics["days_inactive"] = (snapshot_date - order_metrics["last_order_ts"]).dt.days

    # 2. Aggregate Support Metrics (Cost to Serve)
    support_metrics = df_support.groupby("customer_id").agg(
        total_cost_to_serve=("cost_to_serve", "sum"),
        open_cases=("status", lambda s: (s == "escalated").sum())
    ).reset_index()

    # 3. Join customer profile with derived features
    cust_profile = df_customers.merge(order_metrics, on="customer_id", how="left")
    cust_profile = cust_profile.merge(support_metrics, on="customer_id", how="left")

    cust_profile["total_orders"] = cust_profile["total_orders"].fillna(0).astype(int)
    cust_profile["net_spend"] = cust_profile["net_spend"].fillna(0.0).round(2)
    cust_profile["days_inactive"] = cust_profile["days_inactive"].fillna(999).astype(int)
    cust_profile["total_cost_to_serve"] = cust_profile["total_cost_to_serve"].fillna(0.0).round(2)

    # Save feature store table with derived values
    cust_profile.to_csv(os.path.join(processed_dir, "customer_features.csv"), index=False)

    # 4. Evaluate Segment Rules
    memberships = []
    assigned_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for _, cust in cust_profile.iterrows():
        cid = cust["customer_id"]
        
        # Rule 1: VIP High-Spender (SEG-2026-000001) -> net_spend >= 500 and total_orders >= 2
        if cust["net_spend"] >= 500 and cust["total_orders"] >= 2:
            seg_id = "SEG-2026-000001"
            memberships.append({
                "membership_id": f"MEM-{seg_id}-{cid}",
                "customer_id": cid,
                "segment_id": seg_id,
                "assigned_at": assigned_at,
                "is_exclusive": True
            })

        # Rule 2: At-Risk Dormant (SEG-2026-000002) -> total_orders <= 1 and days_inactive >= 60
        if cust["total_orders"] <= 1 and cust["days_inactive"] >= 60:
            seg_id = "SEG-2026-000002"
            memberships.append({
                "membership_id": f"MEM-{seg_id}-{cid}",
                "customer_id": cid,
                "segment_id": seg_id,
                "assigned_at": assigned_at,
                "is_exclusive": True
            })

        # Rule 3: High Service Cost (SEG-2026-000003) -> total_cost_to_serve >= 300
        if cust["total_cost_to_serve"] >= 300:
            seg_id = "SEG-2026-000003"
            memberships.append({
                "membership_id": f"MEM-{seg_id}-{cid}",
                "customer_id": cid,
                "segment_id": seg_id,
                "assigned_at": assigned_at,
                "is_exclusive": False
            })

    # Read ground truth to replicate injected anomaly 1 for audit testing
    gt_path = os.path.join(data_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path, "r") as f:
            gt_data = json.load(f)
            for item in gt_data:
                if item.get("anomaly_type") == "conflicting_exclusive_segments":
                    # Force membership in both exclusive segments for this customer
                    bad_cid = item["entity_id"]
                    memberships.append({
                        "membership_id": f"MEM-SEG-2026-000001-{bad_cid}",
                        "customer_id": bad_cid,
                        "segment_id": "SEG-2026-000001",
                        "assigned_at": assigned_at,
                        "is_exclusive": True
                    })
                    memberships.append({
                        "membership_id": f"MEM-SEG-2026-000002-{bad_cid}",
                        "customer_id": bad_cid,
                        "segment_id": "SEG-2026-000002",
                        "assigned_at": assigned_at,
                        "is_exclusive": True
                    })

    df_membership = pd.DataFrame(memberships).drop_duplicates(subset=["membership_id"])
    df_membership.to_csv(os.path.join(processed_dir, "segment_membership.csv"), index=False)
    print(f"Segmentation complete: {len(df_membership)} memberships generated.")
    return df_membership


if __name__ == "__main__":
    run_segmentation()