import os
from datetime import datetime, UTC
from uuid import uuid4

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


app = FastAPI(
    title="Inventory Service",
    description="Handles item creation and item lookup.",
    version="0.1.0",
)

setup_logging("inventory-service")
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


class ItemCreate(BaseModel):
    name: str
    stock: int
    price: float


class ItemResponse(BaseModel):
    item_id: str
    name: str
    stock: int
    price: float
    created_at: str


def get_connection():
    return psycopg.connect(DATABASE_URL)


@app.on_event("startup")
def startup():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    stock INTEGER NOT NULL,
                    price DOUBLE PRECISION NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )


@app.get("/health")
def health_check():
    return {
        "service": "inventory-service",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/items", response_model=ItemResponse)
def create_item(item: ItemCreate):
    if item.stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative")

    if item.price < 0:
        raise HTTPException(status_code=400, detail="Price cannot be negative")

    item_id = str(uuid4())
    created_at = datetime.now(UTC)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO items (item_id, name, stock, price, created_at)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (item_id, item.name, item.stock, item.price, created_at),
            )
    logger.info(
    "item created",
    extra={
        "item_id": item_id,
    },
)

    return ItemResponse(
        item_id=item_id,
        name=item.name,
        stock=item.stock,
        price=item.price,
        created_at=created_at.isoformat(),
    )


@app.get("/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT item_id, name, stock, price, created_at
                FROM items
                WHERE item_id = %s;
                """,
                (item_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Item not found")

    return ItemResponse(
        item_id=row[0],
        name=row[1],
        stock=row[2],
        price=row[3],
        created_at=row[4].isoformat(),
    )