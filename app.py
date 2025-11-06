# app.py
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from datetime import datetime
import httpx

app = FastAPI()

# === Mount static files (for style.css) ===
app.mount("/static", StaticFiles(directory="."), name="static")

# === Templates ===
templates = Jinja2Templates(directory="templates")

# === HARDCODED SUPABASE CREDENTIALS (as requested) ===
SUPABASE_URL = "https://enciwuvvqhnkkfourhkm.supabase.co"
SUPABASE_KEY = "sb_publishable_6cA5-fNu24sHcHxENX474Q__oCrovZR"

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Dashboard page
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            wallets_resp = await client.get(f"{SUPABASE_URL}/rest/v1/wallets", headers=HEADERS)
            txs_resp = await client.get(f"{SUPABASE_URL}/rest/v1/transactions?order=id.desc&limit=20", headers=HEADERS)
            wallets_resp.raise_for_status()
            txs_resp.raise_for_status()
            wallets = wallets_resp.json()
            txs = txs_resp.json()
    except Exception as e:
        return HTMLResponse(f"<h1>Connection Error</h1><pre>{str(e)}</pre>", status_code=500)

    return templates.TemplateResponse(
        "index.html", {"request": request, "wallets": wallets, "txs": txs}
    )

# Receive transaction from bot or demo
@app.post("/api/tx")
async def receive_tx(data: dict):
    try:
        address = data.get("address")
        if not address:
            return JSONResponse({"status": "error", "error": "address required"}, status_code=400)

        payload_tx = {
            "txid": data.get("txid") or "demo-tx",
            "address": address,
            "amount": data.get("amount") or "0.0",
            "timestamp": data.get("timestamp") or datetime.utcnow().isoformat()
        }
        label = data.get("label") or "demo"

        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{SUPABASE_URL}/rest/v1/transactions", headers=HEADERS, json=payload_tx)

            wallet_check = await client.get(f"{SUPABASE_URL}/rest/v1/wallets?address=eq.{address}", headers=HEADERS)
            wallet_data = wallet_check.json()

            if wallet_data:
                await client.patch(
                    f"{SUPABASE_URL}/rest/v1/wallets?address=eq.{address}",
                    headers=HEADERS,
                    json={"last_balance": payload_tx["amount"]}
                )
            else:
                await client.post(
                    f"{SUPABASE_URL}/rest/v1/wallets",
                    headers=HEADERS,
                    json={"user_id": "demo", "label": label, "address": address, "last_balance": payload_tx["amount"]}
                )
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

# Add wallet manually
@app.post("/add_wallet")
async def add_wallet(user_id: str = Form(...), label: str = Form(...), address: str = Form(...)):
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/wallets",
                headers=HEADERS,
                json={"user_id": user_id, "label": label, "address": address, "last_balance": "0"}
            )
        return JSONResponse({"status": "ok"})
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)
