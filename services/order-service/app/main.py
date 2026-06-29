import os
from datetime import datetime, UTC
from typing import Dict
from uuid import uuid4

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://incident_user:incident_password@localhost:5432/incident_db",
)


app = FastAPI(
    title="Order Service",
    description="Handles order creation and order lookup.",
    version="0.1.0",
)


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