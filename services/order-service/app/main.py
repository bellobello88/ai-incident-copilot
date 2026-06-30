import os
from datetime import datetime, UTC
from uuid import uuid4

import httpx
import psycopg
from fastapi import FastAPI, HTTPException, Request
from app.logging_config import setup_logging
from pydantic import BaseModel

import logging
import time
import uuid


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://incident_user:incident_password@localhost:5432/incident_db",
)

USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8002")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8003")


app = FastAPI(
    title="Order Service",
    description="Handles order creation and order lookup.",
    version="0.1.0",
)
setup_logging("order-service")
logger = logging.getLogger(__name__)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.info(
            "request completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            },
        )

        response.headers["X-Request-ID"] = request_id
        return response

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        logger.exception(
            "request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": 500,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
                "error_type": type(exc).__name__,
            },
        )

        raise


class OrderCreate(BaseModel):
    user_id: str
    item_id: str
    quantity: int


class OrderResponse(BaseModel):
    order_id: str
    user_id: str
    item_id: str
    quantity: int
    status: str
    created_at: str


def get_connection():
    return psycopg.connect(DATABASE_URL)


def validate_user_exists(user_id: str):
    try:
        response = httpx.get(
            f"{USER_SERVICE_URL}/users/{user_id}",
            timeout=2.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="User service unavailable",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail="User does not exist",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="User service error",
        )


def validate_item_exists(item_id: str, quantity: int):
    try:
        response = httpx.get(
            f"{INVENTORY_SERVICE_URL}/items/{item_id}",
            timeout=2.0,
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Inventory service unavailable",
        )

    if response.status_code == 404:
        raise HTTPException(
            status_code=400,
            detail="Item does not exist",
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=503,
            detail="Inventory service error",
        )

    item = response.json()

    if item["stock"] < quantity:
        raise HTTPException(
            status_code=400,
            detail="Not enough stock",
        )


@app.on_event("startup")
def startup():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    order_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )


@app.get("/health")
def health_check():
    return {
        "service": "order-service",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/orders", response_model=OrderResponse)
def create_order(order: OrderCreate):
    if order.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be positive")

    validate_user_exists(order.user_id)
    validate_item_exists(order.item_id, order.quantity)

    order_id = str(uuid4())
    status = "created"
    created_at = datetime.now(UTC)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (order_id, user_id, item_id, quantity, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s);
                """,
                (
                    order_id,
                    order.user_id,
                    order.item_id,
                    order.quantity,
                    status,
                    created_at,
                ),
            )
    logger.info(
    "order created",
    extra={
        "order_id": order_id,
        "user_id": order.user_id,
        "item_id": order.item_id,
    },
)

    return OrderResponse(
        order_id=order_id,
        user_id=order.user_id,
        item_id=order.item_id,
        quantity=order.quantity,
        status=status,
        created_at=created_at.isoformat(),
    )


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT order_id, user_id, item_id, quantity, status, created_at
                FROM orders
                WHERE order_id = %s;
                """,
                (order_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        order_id=row[0],
        user_id=row[1],
        item_id=row[2],
        quantity=row[3],
        status=row[4],
        created_at=row[5].isoformat(),
    )