"""
Manual WebSocket smoke test for Prepwise.

Run with:
    python -m tests.runtime.wscat_test

Requires env vars:
    TEST_USER_EMAIL
    TEST_USER_PASSWORD
    APP_BASE_URL   (default: http://localhost:8000)
    WS_BASE_URL    (default: ws://localhost:8000)

What it does:
    1. Logs in via HTTP to get a real access token
    2. Decodes the token to extract user_id
    3. Opens a WebSocket connection with that token
    4. Sends a job-search message
    5. Prints every message received for up to 30 seconds
    6. Cleanly disconnects and prints a summary
"""
import asyncio
import json
import os
import sys
import httpx
import websockets

from app.core.security import decode_access_token

APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000")
WS_BASE_URL = os.environ.get("WS_BASE_URL", "ws://localhost:8000")
LISTEN_TIMEOUT_SECONDS = 30
TEST_MESSAGE = "Find me ML engineering roles in Nairobi"

def _separator(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}\n")


async def _login() -> tuple[str, str]:
    email = os.environ["TEST_USER_EMAIL"]
    password = os.environ["TEST_USER_PASSWORD"]

    _separator("Step 1 — Login")
    print(f"Email    : {email}")
    print(f"Endpoint : {APP_BASE_URL}/api/auth/login")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{APP_BASE_URL}/api/auth/login",
            json={"email": email, "password": password},
        )

    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code}")
        print(resp.text)
        sys.exit(1)

    access_token = resp.json()["access_token"]
    print(f"Login OK — token length: {len(access_token)}")
    return access_token, email

async def _connect_and_listen(access_token: str) -> None:
    decoded = decode_access_token(access_token)
    user_id = decoded["user_id"]

    ws_url = f"{WS_BASE_URL}/ws/{user_id}?token={access_token}"

    _separator("Step 2 — WebSocket Connection")
    print(f"User ID  : {user_id}")
    print(f"URL      : {ws_url[:80]}...")

    received_types: list[str] = []

    async with websockets.connect(ws_url) as ws:
        print("Connection accepted.\n")

        _separator("Step 3 — Sending Message")
        payload = {
            "type": "message",
            "chat_id": None,
            "engine_type": None,
            "content": TEST_MESSAGE,
        }
        print(f"Content  : {TEST_MESSAGE}")
        await ws.send(json.dumps(payload))
        print("Message sent.\n")

        _separator("Step 4 — Receiving Messages")

        async def _listen():
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    print(f"[raw]    {raw!r}")
                    continue

                msg_type = msg.get("type", "unknown")
                received_types.append(msg_type)

                if msg_type == "token":
                    print(msg.get("content", ""), end="", flush=True)
                elif msg_type == "status":
                    print(f"\n[status] {msg.get('content', '')}")
                elif msg_type == "thinking":
                    print(f"[think]  {msg.get('content', '')}")
                elif msg_type == "done":
                    print(f"\n[done]   chat_id={msg.get('chat_id')}  engine={msg.get('engine_type')}  title={msg.get('title')!r}")
                    return
                elif msg_type == "error":
                    print(f"\n[error]  {msg.get('content', '')}")
                    return
                else:
                    print(f"\n[{msg_type}] {msg}")

        try:
            await asyncio.wait_for(_listen(), timeout=LISTEN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            print(f"\n[timeout] No done/error received within {LISTEN_TIMEOUT_SECONDS}s")

    _separator("Summary")
    print(f"Message types received : {received_types}")
    has_content = "token" in received_types or "status" in received_types
    print(f"Smoke test result      : {'PASS' if has_content else 'FAIL — no content received'}")

async def main() -> None:
    for var in ("TEST_USER_EMAIL", "TEST_USER_PASSWORD"):
        if not os.environ.get(var):
            print(f"Missing required env var: {var}")
            sys.exit(1)

    access_token, _ = await _login()
    await _connect_and_listen(access_token)

if __name__ == "__main__":
    asyncio.run(main())
