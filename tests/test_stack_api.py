import os
import time
import uuid

import requests


ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8001")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8003")
ANOMALY_DETECTOR_URL = os.getenv("ANOMALY_DETECTOR_URL", "http://localhost:8004")
TRAFFIC_GENERATOR_URL = os.getenv("TRAFFIC_GENERATOR_URL", "http://localhost:8005")


def get_json(url: str):
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def post_json(url: str, payload=None):
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    return response.json()


def test_health_endpoints():
    services = {
        "order-service": f"{ORDER_SERVICE_URL}/health",
        "user-service": f"{USER_SERVICE_URL}/health",
        "inventory-service": f"{INVENTORY_SERVICE_URL}/health",
        "anomaly-detector": f"{ANOMALY_DETECTOR_URL}/health",
        "traffic-generator": f"{TRAFFIC_GENERATOR_URL}/health",
    }

    for service_name, url in services.items():
        data = get_json(url)

        assert data["service"] == service_name
        assert data["status"] == "ok"
        assert "timestamp" in data


def test_create_user_item_and_order_flow():
    unique_id = uuid.uuid4().hex[:8]

    user = post_json(
        f"{USER_SERVICE_URL}/users",
        {
            "name": f"Test User {unique_id}",
            "email": f"test-{unique_id}@example.com",
        },
    )

    assert "user_id" in user
    assert user["name"] == f"Test User {unique_id}"

    item = post_json(
        f"{INVENTORY_SERVICE_URL}/items",
        {
            "name": f"Test Item {unique_id}",
            "stock": 10,
            "price": 29.99,
        },
    )

    assert "item_id" in item
    assert item["stock"] == 10

    order = post_json(
        f"{ORDER_SERVICE_URL}/orders",
        {
            "user_id": user["user_id"],
            "item_id": item["item_id"],
            "quantity": 2,
        },
    )

    assert "order_id" in order
    assert order["user_id"] == user["user_id"]
    assert order["item_id"] == item["item_id"]
    assert order["quantity"] == 2
    assert order["status"] == "created"

    fetched_order = get_json(f"{ORDER_SERVICE_URL}/orders/{order['order_id']}")

    assert fetched_order["order_id"] == order["order_id"]
    assert fetched_order["user_id"] == user["user_id"]
    assert fetched_order["item_id"] == item["item_id"]


def test_order_rejects_missing_user():
    response = requests.post(
        f"{ORDER_SERVICE_URL}/orders",
        json={
            "user_id": "missing-user",
            "item_id": "missing-item",
            "quantity": 1,
        },
        timeout=10,
    )

    assert response.status_code in [400, 503]


def test_failure_injection_endpoints():
    error_response = requests.get(f"{ORDER_SERVICE_URL}/simulate/error", timeout=10)
    assert error_response.status_code == 500

    slow_response = requests.get(
        f"{USER_SERVICE_URL}/simulate/slow",
        params={"delay_seconds": 1},
        timeout=10,
    )
    assert slow_response.status_code == 200

    data = slow_response.json()
    assert data["status"] == "slow request completed"


def test_anomaly_report_shape():
    report = get_json(f"{ANOMALY_DETECTOR_URL}/report")

    assert "service" in report
    assert "status" in report
    assert "checked_at" in report
    assert "incident_count" in report
    assert "summary" in report
    assert "root_cause_hypothesis" in report
    assert "recommended_actions" in report
    assert "incidents" in report


def test_llm_report_fallback_shape():
    report = get_json(f"{ANOMALY_DETECTOR_URL}/report/llm")

    assert "service" in report
    assert "llm_enabled" in report
    assert "llm_analysis" in report
    assert "base_report" in report


def test_traffic_generator_normal():
    response = requests.post(
        f"{TRAFFIC_GENERATOR_URL}/generate/normal",
        params={"requests_per_service": 1},
        timeout=20,
    )

    response.raise_for_status()
    data = response.json()

    assert data["scenario"] == "normal"
    assert data["total_requests"] >= 3
    assert "successful_requests" in data
    assert "failed_requests" in data
    assert "details" in data


def test_traffic_generator_mixed_creates_detectable_activity():
    response = requests.post(
        f"{TRAFFIC_GENERATOR_URL}/generate/mixed",
        timeout=30,
    )

    response.raise_for_status()
    data = response.json()

    assert data["scenario"] == "mixed"
    assert data["total_requests"] > 0

    time.sleep(10)

    report = get_json(f"{ANOMALY_DETECTOR_URL}/report")

    assert "status" in report
    assert "incident_count" in report
