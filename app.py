from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import uuid
import time
import base64

app = FastAPI()

# -----------------------------
# Enable CORS
# -----------------------------
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Fixed catalog of 45 orders
# -----------------------------

TOTAL_ORDERS = 45

catalog = [
    {
        "id": i,
        "item": f"Item {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# -----------------------------
# Idempotency storage
# -----------------------------

idempotency_store = {}

# -----------------------------
# Rate limiting storage
# -----------------------------

RATE_LIMIT = 20
WINDOW = 10

client_requests = {}


# -----------------------------
# Rate limit helper
# -----------------------------

def check_rate_limit(client_id: str):
    now = time.time()

    if client_id not in client_requests:
        client_requests[client_id] = []

    timestamps = client_requests[client_id]

    timestamps[:] = [
        t for t in timestamps
        if now - t < WINDOW
    ]

    if len(timestamps) >= RATE_LIMIT:

        retry = WINDOW - (now - timestamps[0])

        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={
                "Retry-After": str(int(retry) + 1)
            },
        )

    timestamps.append(now)


# -----------------------------
# POST /orders
# -----------------------------

@app.post("/orders", status_code=201)
def create_order(
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    client_id: str = Header(..., alias="X-Client-Id"),
):

    check_rate_limit(client_id)

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        "status": "created"
    }

    idempotency_store[idempotency_key] = order

    return order


# -----------------------------
# Cursor encode
# -----------------------------

def encode_cursor(index: int):

    return base64.b64encode(
        str(index).encode()
    ).decode()


def decode_cursor(cursor: Optional[str]):

    if not cursor:
        return 0

    try:
        return int(
            base64.b64decode(cursor).decode()
        )

    except:
        return 0


# -----------------------------
# GET /orders
# -----------------------------

@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: str = Header(..., alias="X-Client-Id"),
):

    check_rate_limit(x_client_id)

    start = decode_cursor(cursor)

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = encode_cursor(end)

    return {
        "items": items,
        "next_cursor": next_cursor,
    }