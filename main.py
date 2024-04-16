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

        response = None
        if action == "buy":
            if current_position == "Sell":  # Closing a short and opening a long
                response = complete_position_change('Buy', symbol, qty)
            elif not current_position:  # No position, opening a long
                response = session.place_order(
                    category="linear", symbol=symbol, side="Buy", orderType="Market", qty=qty)
                current_positions[symbol] = "Buy"
        elif action == "sell":
            if current_position == "Buy":  # Closing a long and opening a short
                response = complete_position_change('Sell', symbol, qty)
            elif not current_position:  # No position, opening a short
                response = session.place_order(
                    category="linear", symbol=symbol, side="Sell", orderType="Market", qty=qty)
                current_positions[symbol] = "Sell"

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def complete_position_change(new_position, symbol, qty):
    current_position = current_positions.get(symbol)
    response = None
    if current_position and ((new_position == 'Buy' and current_position == 'Sell') or
                             (new_position == 'Sell' and current_position == 'Buy')):
        # Close the current position
        response = session.place_order(
            category="linear", symbol=symbol, side=current_position,
            orderType="Market", qty=qty, reduce_only=True, close_on_trigger=True)

        # Wait until the order is filled
        while True:
            order_status = session.get_order_status(response['order_id'])
            if order_status['status'] == 'Filled':
                break
            time.sleep(1)  # Adjust this delay as needed

    # Open a new position in the opposite direction
    new_response = session.place_order(
        category="linear", symbol=symbol, side=new_position,
        orderType="Market", qty=qty)

    current_positions[symbol] = new_position
    return {'close_response': response, 'new_position_response': new_response} if response else {'new_position_response': new_response}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)