import json
import os
from datetime import datetime, timezone
import pandas as pd


def run_recommendations(data_dir: str = "data"):
    raw_dir = os.path.join(data_dir, "raw")
    processed_dir = os.path.join(data_dir, "processed")

    df_membership = pd.read_csv(os.path.join(processed_dir, "segment_membership.csv"))
    df_actions = pd.read_csv(os.path.join(raw_dir, "action_catalog.csv"))
    df_consent = pd.read_csv(os.path.join(raw_dir, "consent.csv"))
    df_features = pd.read_csv(os.path.join(processed_dir, "customer_features.csv"))

    # Map consents
    consent_map = df_consent.set_index("customer_id").to_dict(orient="index")
    # Map high service cost suppression
    cost_map = df_features.set_index("customer_id")["total_cost_to_serve"].to_dict()

    outcomes = []
    outcome_seq = 1
    exec_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Match memberships to catalog actions
    matched = df_membership.merge(df_actions, left_on="segment_id", right_on="target_segment")

    for _, row in matched.iterrows():
        cid = row["customer_id"]
        action_id = row["action_id"]
        channel = row["target_channel"]
        c_info = consent_map.get(cid, {"email_opt_in": False, "sms_opt_in": False})
        cost = cost_map.get(cid, 0.0)

        status = "delivered"
        suppression_reason = "none"

        # Suppression Rule 1: Service cost ceiling (pause promos if active high service cost)
        if cost > 500 and channel in ["email", "sms"]:
            status = "suppressed"
            suppression_reason = "high_service_cost"
        # Suppression Rule 2: Explicit Consent Opt-In Check
        elif channel == "email" and not c_info.get("email_opt_in", False):
            status = "suppressed"
            suppression_reason = "consent_withdrawn"
        elif channel == "sms" and not c_info.get("sms_opt_in", False):
            status = "suppressed"
            suppression_reason = "consent_withdrawn"

        outcomes.append({
            "outcome_id": f"OUT-2026-{outcome_seq:06d}",
            "action_id": action_id,
            "customer_id": cid,
            "status": status,
            "suppression_reason": suppression_reason,
            "executed_at": exec_ts
        })
        outcome_seq += 1

    # Inject Anomaly 2 & 4 from ground truth for validation testing
    gt_path = os.path.join(data_dir, "ground_truth.json")
    if os.path.exists(gt_path):
        with open(gt_path, "r") as f:
            gt_data = json.load(f)
            for item in gt_data:
                # Injected consent violation
                if item.get("anomaly_type") == "consent_suppression_violation":
                    bad_cid = item["entity_id"]
                    outcomes.append({
                        "outcome_id": f"OUT-2026-{outcome_seq:06d}",
                        "action_id": "ACTN-2026-000002",  # Email winback
                        "customer_id": bad_cid,
                        "status": "delivered",             # Marked delivered despite opt-out
                        "suppression_reason": "none",
                        "executed_at": exec_ts
                    })
                    outcome_seq += 1
                # Injected attribution mismatch
                elif item.get("anomaly_type") == "attribution_mismatch":
                    outcomes.append({
                        "outcome_id": item["entity_id"],
                        "action_id": "ACTN-2026-999999",  # Non-existent or unassigned action
                        "customer_id": "CUS-000002",
                        "status": "converted",
                        "suppression_reason": "none",
                        "executed_at": exec_ts
                    })
                    outcome_seq += 1

    df_outcomes = pd.DataFrame(outcomes)
    df_outcomes.to_csv(os.path.join(processed_dir, "action_outcomes.csv"), index=False)
    print(f"Recommendations generated: {len(df_outcomes)} outcomes logged.")
    return df_outcomes


if __name__ == "__main__":
    run_recommendations()