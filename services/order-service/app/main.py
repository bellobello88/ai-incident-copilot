from datetime import datetime, UTC
from typing import Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


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


orders: Dict[str, OrderResponse] = {}


@app.get("/health")
def health_check():
    return {
        "service": "order-service",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/orders", response_model=OrderResponse)
def create_order(order: OrderCreate):
    order_id = str(uuid4())

    new_order = OrderResponse(
        order_id=order_id,
        user_id=order.user_id,
        item_id=order.item_id,
        quantity=order.quantity,
        status="created",
        created_at=datetime.now(UTC).isoformat(),
    )

    orders[order_id] = new_order
    return new_order


@app.get("/orders/{order_id}", response_model=OrderResponse)
def get_order(order_id: str):
    if order_id not in orders:
        raise HTTPException(status_code=404, detail="Order not found")

    return orders[order_id]