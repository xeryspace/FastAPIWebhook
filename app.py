import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pybit.unified_trading import HTTP

app = FastAPI()
app.mount("/static", StaticFiles(directory="client"), name="static")

API_KEY = 'n67QZocA3IvOqkidqf'
API_SECRET = 'aXaNhOHhU2XZ3J1y4uIHHJB9kPlIJZb3GAJM'
session = HTTP(testnet=False, api_key=API_KEY, api_secret=API_SECRET)

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
        amount_to_risk_percentage = data.get("amount_to_risk", 5)
        chain_winners = data.get("chain_winners", True)

        if not stop_loss or not isinstance(stop_loss, (int, float)):
            raise HTTPException(status_code=400, detail="Invalid stop_loss value")

        # Get account balance
        account_info = session.get_wallet_balance(accountType="UNIFIED")
        if 'result' not in account_info:
            raise HTTPException(status_code=500, detail=f"Error fetching account info: {account_info.get('retMsg', 'Unknown error')}")
        account_balance = float(account_info['result']['list'][0]['totalEquity'])

        # Calculate amount to risk
        amount_to_risk = account_balance * (amount_to_risk_percentage / 100)

        # Get current price
        ticker = session.get_tickers(category="linear", symbol="ETHUSDT")
        if 'result' not in ticker or 'list' not in ticker['result']:
            raise HTTPException(status_code=500, detail=f"Error fetching current price: {ticker.get('retMsg', 'Unknown error')}")
        current_price = float(ticker['result']['list'][0]['lastPrice'])

        # Determine position side
        position_side = "Buy" if stop_loss < current_price else "Sell"

        # Calculate quantity
        quantity = round(amount_to_risk / abs(current_price - stop_loss), 2)

        # Adjust risk if chain_winners is True
        if chain_winners:
            closed_pnl = session.get_closed_pnl(category="linear", symbol="ETHUSDT", limit=2)
            if 'result' in closed_pnl and 'list' in closed_pnl['result']:
                trade_list = closed_pnl['result']['list']
                if len(trade_list) == 2:
                    last_trade_pnl = float(trade_list[0]['closedPnl'])
                    prev_trade_pnl = float(trade_list[1]['closedPnl'])
                    if last_trade_pnl > 0 and prev_trade_pnl > 0:
                        amount_to_risk += last_trade_pnl
                    for i, trade in enumerate(trade_list, start=1):
                        pnl = float(trade['closedPnl'])
                        logger.info(f"Last {i} trade PnL for ETHUSDT: {pnl}")
            else:
                logger.warning(f"Failed to retrieve closed PnL for ETHUSDT")

        # Place order
        order_params = {
            "category": "linear",
            "symbol": "ETHUSDT",
            "side": position_side,
            "orderType": "Market",
            "qty": quantity,
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
        logger.info(f"Market {position_side.lower()} order placed for ETHUSDT with stop-loss at {stop_loss}")

        return {"status": "success", "message": f"Market {'long' if position_side == 'Buy' else 'short'} order placed"}

    except Exception as e:
        logger.error(f"ERROR - Error in trade: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
