from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
import json
import time

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

# Dictionary to store positions of multiple symbols
current_positions = {}

@app.get("/")
async def read_root():
    return {"name": "my-app", "version": "Hello world! From FastAPI running on Uvicorn."}

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        query_params = dict(request.query_params)
        passphrase = query_params.get("passphrase", "")
        if passphrase != "Armjansk12!!":
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        body = await request.json()
        symbol = body.get("symbol")  # Get the symbol like 'DEGENUSDT' or 'WIFUSDT'
        qty = body.get("qty")
        action = body.get("action")

        # Initialize current_position for the symbol if it does not exist
        if symbol not in current_positions:
            current_positions[symbol] = None

        # Get current position for the specific symbol
        current_position = current_positions[symbol]

        if action not in ['buy', 'sell']:
            return {"status": "ignored", "reason": f"Invalid action: {action}"}

        if current_position is None:
            if action == "sell":
                open_position('Sell', symbol, qty)
                print('Case 1: Opened a Short')
            elif action == "buy":
                open_position('Buy', symbol, qty)
                print('Case 2: Opened a Long')
        elif current_position == "Buy":
            if action == "buy":
                print('Case 3: Already in a Long, doing nothing')
            elif action == "sell":
                close_position(symbol, qty)
                open_position('Sell', symbol, qty)
                print('Case 4: Closed a Long and Opened a Short')
        elif current_position == "Sell":
            if action == "sell":
                print('Case 5: Already in a Short, doing nothing')
            elif action == "buy":
                close_position(symbol, qty)
                open_position('Buy', symbol, qty)
                print('Case 6: Closed a Short and Opened a Long')

        return {"status": "success", "data": "Position updated"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def open_position(side, symbol, qty):
    session.place_order(
        category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    current_positions[symbol] = side

def close_position(symbol, qty):
    current_position = current_positions[symbol]
    if current_position == "Buy":
        session.place_order(
            category="linear", symbol=symbol, side="sell",
            orderType="Market", qty=qty, reduce_only=True, close_on_trigger=True)
    elif current_position == "Sell":
        session.place_order(
            category="linear", symbol=symbol, side="buy",
            orderType="Market", qty=qty, reduce_only=True, close_on_trigger=True)
    current_positions[symbol] = None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)