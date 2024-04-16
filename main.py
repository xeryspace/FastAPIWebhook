from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
import json
import time

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

# Dictionary to store positions of multiple symbolss
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
 
        # Check if the received action is different from the current position
        if action not in ['buy', 'sell'] or (action == current_position):
            return {"status": "ignored",
                    "reason": f"Received {action} signal for {symbol} but already in {current_position} position."}

        response = None
        if action == "buy" and current_position == "Sell":  # Closing a short and opening a long
            short_to_long(symbol, qty)
            print('Closed a Short and Opened a Long')
        elif action == "sell" and current_position == "Buy":  # Closing a long and opening a short
            long_to_short(symbol, qty)
            print('Closed a Long and Opened a Short')
        elif action == "buy" and not current_position:  # No position, opening a long
            open_position('Buy', symbol, qty)
            print('Just opened a Long')
        elif action == "sell" and not current_position:  # No position, opening a short
            open_position('Sell', symbol, qty)
            print('Just opened a Short')

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def open_position(side, symbol, qty):
    session.place_order(
        category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    current_positions[symbol] = side

def short_to_long(symbol, qty):
    session.place_order(
        category="linear", symbol=symbol, side="buy", orderType="Market", qty=qty)

    time.sleep(10)  # Increased timeout

    session.place_order(
        category="linear", symbol=symbol, side="buy", orderType="Market", qty=qty)

    current_positions[symbol] = "Buy"  # Update the current position

def long_to_short(symbol, qty):
    # first closing with recude_only
    session.place_order(
        category="linear", symbol=symbol, side="buy",
        orderType="Market", qty=qty, reduce_only=True, close_on_trigger=True)

    time.sleep(10)  # Increased timeout

    # now just opening a new short pos.
    session.place_order(
        category="linear", symbol=symbol, side="sell", orderType="Market", qty=qty)

    current_positions[symbol] = "Sell"  # Update the current position


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)