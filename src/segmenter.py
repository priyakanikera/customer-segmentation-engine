import json
import os
import pandas as pd


def run_segmentation(data_dir: str = "data"):
    raw_dir = os.path.join(data_dir, "raw")
    processed_dir = os.path.join(data_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)

    df_customers = pd.read_csv(os.path.join(raw_dir, "customers.csv"))
    df_orders = pd.read_csv(os.path.join(raw_dir, "orders.csv"))
    df_support = pd.read_csv(os.path.join(raw_dir, "support_cases.csv"))

    # Convert timestamps
    df_orders["order_timestamp"] = pd.to_datetime(df_orders["order_timestamp"], utc=True)
    df_support["opened_at"] = pd.to_datetime(df_support["opened_at"], utc=True)

    # Fixed deterministic reference snapshot date (end of simulation timeline)
    snapshot_date = pd.to_datetime("2026-11-01T00:00:00Z", utc=True)
    assigned_at = "2026-11-01T00:00:00Z"

    # 1. Aggregate Order Metrics (Correct Net Spend Arithmetic)
    # Exclude cancelled orders; net returned orders from completed orders
    valid_orders = df_orders[df_orders["order_status"].isin(["completed", "returned"])].copy()
    valid_orders["signed_amount"] = valid_orders["net_amount"].where(
        valid_orders["order_status"] == "completed",
        -valid_orders["net_amount"]
    )

    order_metrics = valid_orders.groupby("customer_id", as_index=False).agg(
        total_orders=("order_id", "count"),
        net_spend=("signed_amount", "sum"),
        last_order_ts=("order_timestamp", "max")
    )
    order_metrics["days_inactive"] = (snapshot_date - order_metrics["last_order_ts"]).dt.days

    # 2. Aggregate Support Metrics (Cost to Serve)
    support_metrics = df_support.groupby("customer_id", as_index=False).agg(
        total_cost_to_serve=("cost_to_serve", "sum"),
        open_cases=("status", lambda s: (s == "escalated").sum())
    )

    # 3. Join customer profile with derived features
    cust_profile = df_customers.merge(order_metrics, on="customer_id", how="left")
    cust_profile = cust_profile.merge(support_metrics, on="customer_id", how="left")

    cust_profile["total_orders"] = cust_profile["total_orders"].fillna(0).astype(int)
    cust_profile["net_spend"] = cust_profile["net_spend"].fillna(0.0).round(2)
    cust_profile["days_inactive"] = cust_profile["days_inactive"].fillna(999).astype(int)
    cust_profile["total_cost_to_serve"] = cust_profile["total_cost_to_serve"].fillna(0.0).round(2)
    cust_profile["open_cases"] = cust_profile["open_cases"].fillna(0).astype(int)

    # 4. Evaluate Segment Rules (Vectorized for fast execution at 50k+ scale)
    membership_frames = []

    # Rule 1: VIP High-Spender (SEG-2026-000001) -> net_spend >= 500 and total_orders >= 2
    vip_mask = (cust_profile["net_spend"] >= 500) & (cust_profile["total_orders"] >= 2)
    vip_cids = cust_profile.loc[vip_mask, "customer_id"]
    if not vip_cids.empty:
        membership_frames.append(pd.DataFrame({
            "membership_id": "MEM-SEG-2026-000001-" + vip_cids,
            "customer_id": vip_cids,
            "segment_id": "SEG-2026-000001",
            "assigned_at": assigned_at,
            "is_exclusive": True
        }))

    # Rule 2: At-Risk Dormant (SEG-2026-000002) -> total_orders <= 1 and days_inactive >= 60
    dormant_mask = (cust_profile["total_orders"] <= 1) & (cust_profile["days_inactive"] >= 60)
    dormant_cids = cust_profile.loc[dormant_mask, "customer_id"]
    if not dormant_cids.empty:
        membership_frames.append(pd.DataFrame({
            "membership_id": "MEM-SEG-2026-000002-" + dormant_cids,
            "customer_id": dormant_cids,
            "segment_id": "SEG-2026-000002",
            "assigned_at": assigned_at,
            "is_exclusive": True
        }))

    # Rule 3: High Service Cost (SEG-2026-000003) -> total_cost_to_serve >= 300
    cost_mask = cust_profile["total_cost_to_serve"] >= 300
    cost_cids = cust_profile.loc[cost_mask, "customer_id"]
    if not cost_cids.empty:
        membership_frames.append(pd.DataFrame({
            "membership_id": "MEM-SEG-2026-000003-" + cost_cids,
            "customer_id": cost_cids,
            "segment_id": "SEG-2026-000003",
            "assigned_at": assigned_at,
            "is_exclusive": False
        }))

    # 5. Inject Ground-Truth Anomalies (#1 Conflicting Segments & #3 Return Not Netted)
    gt_path = os.path.join(data_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path, "r") as f:
            gt_data = json.load(f)
            for item in gt_data:
                if item.get("anomaly_type") == "conflicting_exclusive_segments":
                    bad_cid = item["entity_id"]
                    membership_frames.append(pd.DataFrame([
                        {
                            "membership_id": f"MEM-SEG-2026-000001-{bad_cid}",
                            "customer_id": bad_cid,
                            "segment_id": "SEG-2026-000001",
                            "assigned_at": assigned_at,
                            "is_exclusive": True
                        },
                        {
                            "membership_id": f"MEM-SEG-2026-000002-{bad_cid}",
                            "customer_id": bad_cid,
                            "segment_id": "SEG-2026-000002",
                            "assigned_at": assigned_at,
                            "is_exclusive": True
                        }
                    ]))
                elif item.get("anomaly_type") == "return_not_netted":
                    bad_oid = item["entity_id"]
                    order_row = df_orders[df_orders["order_id"] == bad_oid]
                    if not order_row.empty:
                        bad_cid = order_row.iloc[0]["customer_id"]
                        returned_amt = order_row.iloc[0]["net_amount"]
                        # Add back 2x returned_amt to simulate failing to deduct the return
                        cust_profile.loc[cust_profile["customer_id"] == bad_cid, "net_spend"] += (2 * returned_amt)

    cust_profile["net_spend"] = cust_profile["net_spend"].round(2)
    cust_profile.to_csv(os.path.join(processed_dir, "customer_features.csv"), index=False)

    if membership_frames:
        df_membership = pd.concat(membership_frames, ignore_index=True).drop_duplicates(subset=["membership_id"])
    else:
        df_membership = pd.DataFrame(columns=["membership_id", "customer_id", "segment_id", "assigned_at", "is_exclusive"])

    df_membership.to_csv(os.path.join(processed_dir, "segment_membership.csv"), index=False)
    print(f"Segmentation complete: {len(df_membership):,} memberships generated.")
    return df_membership


if __name__ == "__main__":
    run_segmentation()