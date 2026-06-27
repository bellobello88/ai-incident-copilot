from datetime import datetime, UTC
from typing import Dict
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


app = FastAPI(
    title="User Service",
    description="Handles user creation and user lookup.",
    version="0.1.0",
)


class UserCreate(BaseModel):
    name: str
    email: str


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    created_at: str


users: Dict[str, UserResponse] = {}


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

    new_user = UserResponse(
        user_id=user_id,
        name=user.name,
        email=user.email,
        created_at=datetime.now(UTC).isoformat(),
    )

    users[user_id] = new_user
    return new_user


@app.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: str):
    if user_id not in users:
        raise HTTPException(status_code=404, detail="User not found")

    return users[user_id]