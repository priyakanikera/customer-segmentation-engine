import os
import json
import pytest
from src.generator import generate_synthetic_dataset
from src.segmenter import run_segmentation
from src.recommender import run_recommendations
from src.validator import validate_dataset


@pytest.fixture(scope="session")
def setup_pipeline(tmp_path_factory):
    temp_dir = tmp_path_factory.mktemp("test_data")
    data_path = str(temp_dir)
    generate_synthetic_dataset(
        seed=20261022,
        num_customers=100,
        num_orders=400,
        num_events=2000,
        output_dir=data_path
    )
    run_segmentation(data_dir=data_path)
    run_recommendations(data_dir=data_path)
    return data_path


def test_referential_integrity_and_keys(setup_pipeline):
    report = validate_dataset(data_dir=setup_pipeline)
    assert all(report["primary_key_checks"].values()), "All primary keys must be strictly unique"
    assert all(report["foreign_key_checks"].values()), "Foreign key integrity violated"


def test_arithmetic_reconciliation(setup_pipeline):
    report = validate_dataset(data_dir=setup_pipeline)
    assert report["arithmetic_reconciliation"]["order_lines_exact"] is True
    assert report["arithmetic_reconciliation"]["orders_reconciled"] is True


def test_ground_truth_anomaly_detection(setup_pipeline):
    report = validate_dataset(data_dir=setup_pipeline)
    anomalies = report["detected_anomalies"]
    types = [a["anomaly_type"] for a in anomalies]
    assert "conflicting_exclusive_segments" in types
    assert "consent_suppression_violation" in types
    assert "attribution_mismatch" in types