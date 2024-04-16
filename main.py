from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
import json

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)


@app.post("/webhook")
async def handle_webhook(request: Request):
    try:
        query_params = dict(request.query_params)
        passphrase = query_params.get("passphrase", "")
        if passphrase != "Armjansk12!!":
            raise HTTPException(status_code=403, detail="Invalid passphrase")

        body = await request.json()
        qty = body.get("qty")
        action = body.get("action")

        if action == "buy":
            response = session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Buy",
                orderType="Market",
                qty=qty,
            )
        elif action == "sell":
            response = session.place_order(
                category="linear",
                symbol="DEGENUSDT",
                side="Sell",
                orderType="Market",
                qty=qty,
                reduce_only=True,
                close_on_trigger=False,
            )
        else:
            raise HTTPException(status_code=400, detail="Action must be 'buy' or 'sell'")

        return {"status": "success", "data": response}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)