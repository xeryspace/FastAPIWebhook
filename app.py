import asyncio
import json
import logging
import math
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pybit.unified_trading import HTTP

app = FastAPI()
app.mount("/static", StaticFiles(directory="client"), name="static")

api_key = 'n67QZocA3IvOqkidqf'
api_secret = 'aXaNhOHhU2XZ3J1y4uIHHJB9kPlIJZb3GAJM'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    with open("client/index.html") as f:
        return f.read()

@app.post("/trade")
async def trade(request: Request):
    try:
        data = await request.json()
        stop_loss = data.get("stop_loss")
        take_profit = data.get("take_profit")
        amount_to_risk = data.get("amount_to_risk", 50)
        chain_winners = data.get("chain_winners", True)

        if not stop_loss or not isinstance(stop_loss, (int, float)):
            raise HTTPException(status_code=400, detail="Invalid stop_loss value")

        current_price = get_current_price("ETHUSDT")
        open_position("ETHUSDT", amount_to_risk, stop_loss, take_profit, chain_winners)

        if stop_loss < current_price:
            return {"status": "success", "message": "Market long order placed"}
        else:
            return {"status": "success", "message": "Market short order placed"}

    except Exception as e:
        logger.error(f"Error in trade: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_current_price(symbol):
    try:
        ticker = session.get_tickers(category="linear", symbol=symbol)
        if 'result' in ticker and 'list' in ticker['result']:
            last_price = float(ticker['result']['list'][0]['lastPrice'])
            return last_price
        else:
            error_message = ticker.get('retMsg', 'Unknown error')
            raise Exception(f"Failed to retrieve current price for {symbol}. Error: {error_message}")
    except Exception as e:
        logger.error(f"Error in get_current_price: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching current price: {str(e)}")


def open_position(symbol, amount_to_risk, stop_loss, take_profit=None, chain_winners=True):
    try:
        current_price = get_current_price(symbol)
        position_side = "Buy" if stop_loss < current_price else "Sell"

        quantity = amount_to_risk / abs(current_price - stop_loss)
        rounded_quantity = round(quantity, 2)

        closed_pnl = session.get_closed_pnl(
            category="linear",
            symbol=symbol,
            limit=2
        )

        if 'result' in closed_pnl and 'list' in closed_pnl['result']:
            trade_list = closed_pnl['result']['list']
            if chain_winners and len(trade_list) == 2:
                last_trade_pnl = float(trade_list[0]['closedPnl'])
                prev_trade_pnl = float(trade_list[1]['closedPnl'])
                if last_trade_pnl > 0 > prev_trade_pnl:
                    amount_to_risk += last_trade_pnl

            for i, trade in enumerate(trade_list, start=1):
                pnl = float(trade['closedPnl'])
                logger.info(f"Last {i} trade PnL for {symbol}: {pnl}")
        else:
            logger.warning(f"Failed to retrieve closed PnL for {symbol}")

        order_params = {
            "category": "linear",
            "symbol": symbol,
            "side": position_side,
            "orderType": "Market",
            "qty": rounded_quantity,
            "timeInForce": "GoodTillCancel",
            "reduceOnly": False,
            "closeOnTrigger": False,
            "stopLoss": str(stop_loss),
            "slTriggerBy": "LastPrice",
            "slOrderType": "Market",
            "tpslMode": "Full"
        }

        if take_profit is not None:
            order_params["takeProfit"] = str(take_profit)
            order_params["tpTriggerBy"] = "LastPrice"
            order_params["tpOrderType"] = "Market"

        session.place_order(**order_params)
        logger.info(f"Market {position_side.lower()} order placed for {symbol} with stop-loss at {stop_loss}")

    except Exception as e:
        logger.error(f"Error in open_position: {str(e)}")
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)