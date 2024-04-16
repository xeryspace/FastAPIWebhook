from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
import json

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

current_position = None

@app.get("/")
async def read_root():
    return {
        "name": "my-app",
        "version": "Hello world! From FastAPI running on Uvicorn."
    }

@app.post("/webhook")
async def handle_webhook(request: Request):
    global current_position

    try:
        query_params = dict(request.query_params)
        passphrase = query_params.get("passphrase", "")
        if passphrase != "Armjansk12!!":
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        body = await request.json()
        qty = body.get("qty")
        action = body.get("action")

        # Check if the received action is different from the current position
        if action not in ['buy', 'sell'] or (action == current_position):
            # If the action is the same as the current position, ignore it
            return {"status": "ignored", "reason": f"Received {action} signal but already in {current_position} position."}

        response = None
        if action == "buy" and current_position == "Sell":  # Closing a short and opening a long
            session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Buy",
                orderType="Market",
                qty=qty,
                reduce_only=True,
                close_on_trigger=True,
            )
            response = session.place_order(  # Open new long position
                category="linear",
                symbol="DEGENUSDT",
                side="Buy",
                orderType="Market",
                qty=qty,
            )
            current_position = "Buy"
        elif action == "sell" and current_position == "Buy":  # Closing a long and opening a short
            session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Sell",
                orderType="Market",
                qty=qty,
                reduce_only=True,
                close_on_trigger=True,
            )
            response = session.place_order(  # Open new short position
                category="linear",
                symbol="DEGENUSDT",
                side="Sell",
                orderType="Market",
                qty=qty,
            )
            current_position = "Sell"
        elif action == "buy" and not current_position:  # No position, opening a long
            response = session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Buy",
                orderType="Market",
                qty=qty,
            )
            current_position = "Buy"
        elif action == "sell" and not current_position:  # No position, opening a short
            response = session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Sell",
                orderType="Market",
                qty=qty,
            )
            current_position = "Sell"

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)