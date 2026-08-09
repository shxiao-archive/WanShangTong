"""Run against a live API: python tests/smoke_live.py [base_url]."""

import os
import sys

import httpx


base_url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
client = httpx.Client(base_url=base_url, timeout=10, trust_env=False)

health = client.get("/api/v1/health/ready")
health.raise_for_status()


def login(username: str, password: str) -> tuple[str, dict]:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    response.raise_for_status()
    result = response.json()["data"]
    return result["access_token"], result["user"]


merchant_token, merchant_user = login(
    os.environ.get("SMOKE_MERCHANT_USERNAME", "merchant"),
    os.environ["DEMO_MERCHANT_PASSWORD"],
)
operator_token, operator_user = login(
    os.environ.get("SMOKE_OPERATOR_USERNAME", "operator"),
    os.environ["DEMO_OPERATOR_PASSWORD"],
)
merchant_headers = {"Authorization": f"Bearer {merchant_token}"}
operator_headers = {"Authorization": f"Bearer {operator_token}"}

assert merchant_user["role"] == "merchant"
assert operator_user["role"] == "operator"
assert client.get("/api/v1/merchants/1", headers=merchant_headers).status_code == 200
assert client.get("/api/v1/merchants/2", headers=merchant_headers).status_code == 403
assert client.get("/api/v1/dashboard/overview", headers=merchant_headers).status_code == 403

merchant_list = client.get("/api/v1/merchants?page_size=100", headers=operator_headers)
merchant_list.raise_for_status()
assert merchant_list.json()["data"]["total"] >= 6

details = client.get("/api/v1/merchants/1/business-data?days=30", headers=merchant_headers).json()["data"]
summary = client.get("/api/v1/merchants/1/business-summary?days=30", headers=merchant_headers).json()["data"]
assert summary["totals"]["orders"] == sum(row["orders"] for row in details)
assert summary["totals"]["revenue"] == round(sum(row["revenue"] for row in details), 2)

profile = client.get("/api/v1/merchants/1/profile", headers=merchant_headers).json()["data"]
recommendations = client.get("/api/v1/merchants/1/recommendations", headers=merchant_headers).json()["data"]
assert len(profile["evidence"]) == 4
assert 1 <= len(recommendations) <= 3
assert all(item["reasons"] for item in recommendations)

print("live smoke passed: auth, RBAC, summaries, profile and recommendations")
