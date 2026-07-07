from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

T = 45
R = 20
WINDOW = 10

orders_catalog = [{"id": i, "name": f"Order {i}"} for i in range(1, T + 1)]
idempotency_store = {}
rate_store = {}

class OrderCreate(BaseModel):
    item: Optional[str] = "sample"

def check_rate_limit(client_id: str):
    now = time.time()
    window_start = now - WINDOW
    timestamps = rate_store.get(client_id, [])
    timestamps = [ts for ts in timestamps if ts >= window_start]

    if len(timestamps) >= R:
        retry_after = max(1, int(WINDOW - (now - min(timestamps))))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    timestamps.append(now)
    rate_store[client_id] = timestamps

@app.post("/orders", status_code=201)
def create_order(
    payload: OrderCreate,
    request: Request,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    x_client_id: Optional[str] = Header(default="anonymous", alias="X-Client-Id"),
):
    check_rate_limit(x_client_id)

    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header required")

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "item": payload.item,
        "status": "created",
    }
    idempotency_store[idempotency_key] = order
    return order

@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: Optional[str] = Header(default="anonymous", alias="X-Client-Id"),
):
    check_rate_limit(x_client_id)

    limit = max(1, min(limit, 45))

    start_index = 0
    if cursor:
        try:
            last_seen = int(cursor)
            start_index = last_seen
        except ValueError:
            start_index = 0

    items = orders_catalog[start_index:start_index + limit]

    next_cursor = None
    if start_index + limit < len(orders_catalog):
        next_cursor = str(items[-1]["id"])

    return {
        "items": items,
        "next_cursor": next_cursor,
    }