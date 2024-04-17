import asyncio
import time
import json
import logging
from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

        if action not in ['buy', 'sell']:
            return {"status": "ignored", "reason": f"Invalid action: {action}"}

        logger.info(f"Received {action} action for {symbol}")

        # Get the entry price from the Bybit API
        entry_price = get_current_price(symbol)

        # Check the time of the candle
        current_time = datetime.now()
        candle_time = current_time.replace(second=0, microsecond=0)
        next_candle_time = candle_time + timedelta(minutes=(3 - candle_time.minute % 3))
        seconds_remaining = (next_candle_time - current_time).total_seconds()
        if seconds_remaining <= 25:
            await process_signal(symbol, qty, action, entry_price)
        else:
            await asyncio.sleep(25)
            current_price = get_current_price(symbol)
            if action == 'buy' and current_price >= entry_price:
                logger.info(f"Buy Action, Current Price: {current_price}, Entry Price: {entry_price}")
                await process_signal(symbol, qty, action, entry_price)
                await asyncio.sleep(30)
                logger.info(f"Waited another 30 sec, Current Price: {current_price}, Entry Price: {entry_price}")
                logger.info(f"Current Price should be Higher then Entry, since we are Longing")
                if current_price < entry_price:
                    await close_position(symbol, qty)
                    logger.info(f"Should have closed the Long Position")
            elif action == 'sell' and current_price <= entry_price:
                logger.info(f"Sell Action, Current Price: {current_price}, Entry Price: {entry_price}")
                await process_signal(symbol, qty, action, entry_price)
                await asyncio.sleep(30)
                logger.info(f"Waited another 30 sec, Current Price: {current_price}, Entry Price: {entry_price}")
                logger.info(f"Current Price should be Smaller then Entry, since we are Shorting")
                if current_price > entry_price:
                    await close_position(symbol, qty)
                    logger.info(f"Should have closed the Short Position")
            else:
                logger.info(f"Price condition not met after 15 seconds for {symbol}. Signal ignored.")

        return {"status": "success", "data": "Position updated"}

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in the alert message: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        logger.error(f"Error in handle_webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_signal(symbol, qty, action, entry_price):
    try:
        # Retrieve the current position for the symbol
        position_info = session.get_positions(category="linear", symbol=symbol)
        current_position = None
        if position_info['result']['list']:
            current_position = position_info['result']['list'][0]['side']
        if current_position is None or current_position == "":
            if action == "sell":
                open_position('Sell', symbol, qty)
            elif action == "buy":
                open_position('Buy', symbol, qty)
        elif current_position == "Buy":
            if action == "sell":
                close_position(symbol, qty)
                open_position('Sell', symbol, qty)
        elif current_position == "Sell":
            if action == "buy":
                close_position(symbol, qty)
                open_position('Buy', symbol, qty)
    except Exception as e:
        logger.error(f"Error in process_signal: {str(e)}")
        raise

def get_current_price(symbol):
    try:
        ticker = session.get_tickers(category="linear", symbol=symbol)
        if ticker['result']:
            last_price = float(ticker['result']['list'][0]['lastPrice'])
            return last_price
        else:
            raise Exception(f"Failed to retrieve current price for {symbol}")
    except Exception as e:
        logger.error(f"Error in get_current_price: {str(e)}")
        raise

def open_position(side, symbol, qty):
    try:
        session.place_order(
            category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    except Exception as e:
        logger.error(f"Error in open_position: {str(e)}")
        raise

def close_position(symbol, qty):
    try:
        position_info = session.get_positions(category="linear", symbol=symbol)
        if position_info['result']['list']:
            side = "Buy" if position_info['result']['list'][0]['side'] == "Sell" else "Sell"
            session.place_order(
                category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    except Exception as e:
        logger.error(f"Error in close_position: {str(e)}")
        raise

def check_positions():
    symbols = ['FETUSDT', '1000BONKUSDT', 'WIFUSDT', '1000PEPEUSDT']  # Add the symbols you want to check positions for
    while True:
        try:
            for symbol in symbols:
                time.sleep(2)
                positions = session.get_positions(category="linear", symbol=symbol)['result']['list']

                if positions:
                    position = positions[0]  # Get the first position for the symbol
                    symbol = position['symbol']
                    position_idx = position['positionIdx']

                    if 'unrealisedPnl' not in position or position['unrealisedPnl'] == '':
                        continue

                    unrealised_pnl = float(position['unrealisedPnl'])
                    unrealised_pnl_rounded = round(unrealised_pnl, 2)

                    if 'size' in position and position['size'] != '':
                        size = float(position['size'])
                    else:
                        continue
                    if unrealised_pnl >= 1.5:
                        logger.info(f"Closing the entire position for {symbol} ( Profit )")
                        close_position(symbol, size)
                    elif unrealised_pnl <= -1.5:
                        logger.info(f"Closing the entire position for {symbol} ( Loss )")
                        close_position(symbol, size)
                else:
                    continue
            time.sleep(2)  # Delay for 5 seconds before the next iteration

        except Exception as e:
            continue

@app.on_event("startup")
async def startup_event():
    import threading
    threading.Thread(target=check_positions).start()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)