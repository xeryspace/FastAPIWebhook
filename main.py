from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
import json

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

# Dictionary to store positions of multiple symbols
current_positions = {}


@app.get("/")
async def read_root():
    return {
        "name": "my-app",
        "version": "Hello world! From FastAPI running on Uvicorn."
    }


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

        # Check current position for the specific symbol
        current_position = current_positions[symbol]

        # Check if the received action is different from the current position
        if action not in ['buy', 'sell'] or (action == current_position):
            return {"status": "ignored",
                    "reason": f"Received {action} signal for {symbol} but already in {current_position} position."}

        response = None
        if action == "buy" and current_position == "Sell":  # Closing a short and opening a long
            complete_position_change('Buy', symbol, qty)
        elif action == "sell" and current_position == "Buy":  # Closing a long and opening a short
            complete_position_change('Sell', symbol, qty)
        elif action == "buy" and not current_position:  # No position, opening a long
            response = session.place_order(
                category="linear", symbol=symbol, side="Buy", orderType="Market", qty=qty)
            current_positions[symbol] = "Buy"
        elif action == "sell" and not current_position:  # No position, opening a short
            response = session.place_order(
                category="linear", symbol=symbol, side="Sell", orderType="Market", qty=qty)
            current_positions[symbol] = "Sell"

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def complete_position_change(new_position, symbol, qty):
    # This function closes the current position and opens the opposite one
    session.place_order(
        category="linear", symbol=symbol, side=new_position,
        orderType="Market", qty=qty, reduce_only=True, close_on_trigger=True)
    response = session.place_order(
        category="linear", symbol=symbol, side=new_position,
        orderType="Market", qty=qty)
    current_positions[symbol] = new_position
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)