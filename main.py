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
    return {"name": "my-app", "version": "Hello world! From FastAPI running on Uvicorn."}

@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        query_params = dict(request.query_params)
        passphrase = query_params.get("passphrase", "")
        if passphrase != "Armjansk12!!":
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        body = await request.json()
        symbol = body.get("symbol")
        usdt_amount = body.get("usdt_amount")  # Changed from qty to usdt_amount
        action = body.get("action")
        leverage = body.get("leverage", 10)  # Added leverage parameter, defaulting to 10

        if symbol not in current_positions:
            current_positions[symbol] = None

        current_position = current_positions[symbol]

        # Setting leverage
        session.set_leverage(symbol=symbol, leverage=leverage)

        # Check if action is different from current position.
        if action not in ['buy', 'sell'] or (action == current_position):
            return {"status": "ignored",
                    "reason": f"Received {action} signal for {symbol} but already in {current_position} position."}

        response = None
        if action == "buy" and current_position == "Sell":  # Closing a short and opening a long
            response = complete_position_change('Buy', symbol, usdt_amount)
        elif action == "sell" and current_position == "Buy":  # Closing a long and opening a short
            response = complete_position_change('Sell', symbol, usdt_amount)
        elif action == "buy" and not current_position:  # No current position, opening a long
            response = session.place_order(
                category="linear", symbol=symbol, side="Buy", orderType="Market", qty=usdt_amount, marketUnit="quoteCoin")
            current_positions[symbol] = "Buy"
        elif action == "sell" and not current_position:  # No current position, opening a short
            response = session.place_order(
                category="linear", symbol=symbol, side="Sell", orderType="Market", qty=usdt_amount)
            current_positions[symbol] = "Sell"

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def complete_position_change(new_position, symbol, usdt_amount):
    current_position = current_positions.get(symbol)
    if current_position and ((new_position == 'Buy' and current_position == 'Sell') or
                             (new_position == 'Sell' and current_position == 'Buy')):
        response = session.place_order(
            category="linear", symbol=symbol, side=new_position, orderType="Market", qty=usdt_amount, marketUnit="quoteCoin", reduce_only=True, close_on_trigger=True)
    else:
        response = None

    new_response = session.place_order(
        category="linear", symbol=symbol, side=new_position, orderType="Market", qty=usdt_amount, marketUnit="quoteCoin")

    current_positions[symbol] = new_position
    return {'close_response': response, 'new_position_response': new_response} if response else new_response


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)