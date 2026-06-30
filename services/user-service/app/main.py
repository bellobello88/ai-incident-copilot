import os
from datetime import datetime, UTC
from typing import Optional
from uuid import uuid4

import psycopg
from fastapi import FastAPI, HTTPException, Request
from app.logging_config import setup_logging
from pydantic import BaseModel

import logging
import time
import uuid

from app.metrics_config import setup_metrics


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://incident_user:incident_password@localhost:5432/incident_db",
)


app = FastAPI(
    title="User Service",
    description="Handles user creation and user lookup.",
    version="0.1.0",
)

setup_logging("user-service")
logger = logging.getLogger(__name__)

setup_metrics(app, "user-service")

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

class UserCreate(BaseModel):
    name: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    created_at: str


def get_connection():
    return psycopg.connect(DATABASE_URL)


@app.on_event("startup")
def startup():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                );
                """
            )


@app.get("/health")
def health_check():
    return {
        "service": "user-service",
        "status": "ok",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.post("/users", response_model=UserResponse)
def create_user(user: UserCreate):
    user_id = str(uuid4())
    created_at = datetime.now(UTC)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (user_id, name, email, created_at)
                VALUES (%s, %s, %s, %s);
                """,
                (user_id, user.name, user.email, created_at),
            )
    logger.info(
    "user created",
    extra={
        "user_id": user_id,
    },
)

    return UserResponse(
        user_id=user_id,
        name=user.name,
        email=user.email,
        created_at=created_at.isoformat(),
    )


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT user_id, name, email, created_at
                FROM users
                WHERE user_id = %s;
                """,
                (user_id,),
            )
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=row[0],
        name=row[1],
        email=row[2],
        created_at=row[3].isoformat(),
    )