import asyncio
import os
import random
from datetime import datetime, UTC
from typing import Dict, List

import httpx
from fastapi import FastAPI
from pydantic import BaseModel


ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8001")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8003")


SERVICE_URLS = {
    "order-service": ORDER_SERVICE_URL,
    "user-service": USER_SERVICE_URL,
    "inventory-service": INVENTORY_SERVICE_URL,
}


app = FastAPI(
    title="Traffic Generator",
    description="Generates demo traffic for AI Incident Copilot.",
    version="0.1.0",
)


class TrafficResult(BaseModel):
    scenario: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    details: List[Dict]


@app.get("/health")
def health_check():
    return {
        "service": "traffic-generator",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


async def send_get(client: httpx.AsyncClient, url: str) -> Dict:
    try:
        response = await client.get(url, timeout=15.0)

        return {
            "url": url,
            "status_code": response.status_code,
            "ok": response.status_code < 500,
        }

    except httpx.RequestError as exc:
        return {
            "url": url,
            "status_code": None,
            "ok": False,
            "error": str(exc),
        }


def summarize(scenario: str, details: List[Dict]) -> TrafficResult:
    successful = sum(1 for item in details if item.get("ok"))
    failed = len(details) - successful

    return TrafficResult(
        scenario=scenario,
        total_requests=len(details),
        successful_requests=successful,
        failed_requests=failed,
        details=details,
    )


@app.post("/generate/normal", response_model=TrafficResult)
async def generate_normal(requests_per_service: int = 5):
    urls = []

    for service_url in SERVICE_URLS.values():
        for _ in range(requests_per_service):
            urls.append(f"{service_url}/health")

    async with httpx.AsyncClient() as client:
        details = await asyncio.gather(*[send_get(client, url) for url in urls])

    return summarize("normal", details)


@app.post("/generate/errors", response_model=TrafficResult)
async def generate_errors(service_name: str = "order-service", count: int = 5):
    service_url = SERVICE_URLS.get(service_name, ORDER_SERVICE_URL)
    urls = [f"{service_url}/simulate/error" for _ in range(count)]

    async with httpx.AsyncClient() as client:
        details = await asyncio.gather(*[send_get(client, url) for url in urls])

    return summarize("errors", details)


@app.post("/generate/slow", response_model=TrafficResult)
async def generate_slow(service_name: str = "user-service", count: int = 3, delay_seconds: float = 3.0):
    service_url = SERVICE_URLS.get(service_name, USER_SERVICE_URL)
    urls = [
        f"{service_url}/simulate/slow?delay_seconds={delay_seconds}"
        for _ in range(count)
    ]

    async with httpx.AsyncClient() as client:
        details = await asyncio.gather(*[send_get(client, url) for url in urls])

    return summarize("slow", details)


@app.post("/generate/mixed", response_model=TrafficResult)
async def generate_mixed():
    urls = []

    for service_url in SERVICE_URLS.values():
        for _ in range(5):
            urls.append(f"{service_url}/health")

    for _ in range(5):
        urls.append(f"{ORDER_SERVICE_URL}/simulate/error")

    for _ in range(3):
        urls.append(f"{USER_SERVICE_URL}/simulate/slow?delay_seconds=3")

    random.shuffle(urls)

    async with httpx.AsyncClient() as client:
        details = await asyncio.gather(*[send_get(client, url) for url in urls])

    return summarize("mixed", details)
