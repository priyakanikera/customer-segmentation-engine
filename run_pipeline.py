import argparse
import json
from src.generator import generate_synthetic_dataset
from src.segmenter import run_segmentation
from src.recommender import run_recommendations
from src.validator import validate_dataset


def main():
    parser = argparse.ArgumentParser(description="End-to-End Segmentation Engine")
    parser.add_argument("--seed", type=int, default=20261022, help="Seed for reproducibility")
    parser.add_argument("--customers", type=int, default=50000, help="Customer count")
    parser.add_argument("--orders", type=int, default=200000, help="Order count")
    parser.add_argument("--events", type=int, default=1000000, help="Engagement event count")
    args = parser.parse_args()

    print(f"1. Generating synthetic dataset (Seed: {args.seed})...")
    generate_synthetic_dataset(
        seed=args.seed,
        num_customers=args.customers,
        num_orders=args.orders,
        num_events=args.events
    )

    print("2. Running RFM & rule-based customer segmentation...")
    run_segmentation()

    print("3. Executing recommendation engine with consent suppression...")
    run_recommendations()

    print("4. Auditing dataset and calculating evaluation metrics...")
    report = validate_dataset()

    print("\n--- Pipeline Execution Summary ---")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()