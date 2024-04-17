import asyncio
import json
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP
from datetime import datetime, timedelta
from threading import Lock

position_lock = Lock()
position_processing = {}

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
        if seconds_remaining <= 15:
            await process_signal(symbol, qty, action, entry_price)
        else:
            await asyncio.sleep(15)
            current_price = get_current_price(symbol)
            tolerance_percentage = 0.001  # 0.1% tolerance
            if action == 'buy' and current_price >= entry_price * (1 - tolerance_percentage):
                logger.info(f"Buy Action, Current Price: {current_price}, Entry Price: {entry_price}")
                await process_signal(symbol, qty, action, entry_price)
            elif action == 'sell' and current_price <= entry_price * (1 + tolerance_percentage):
                logger.info(f"Sell Action, Current Price: {current_price}, Entry Price: {entry_price}")
                await process_signal(symbol, qty, action, entry_price)
            else:
                logger.info(f"Ignored because {action}-order and:")
                logger.info(f"Entry Price was : {entry_price}")
                logger.info(f"Current Price is : {current_price}")

        return {"status": "success", "data": "Position updated"}

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in the alert message: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        logger.error(f"Error in handle_webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def check_position_exists(symbol):
    try:
        position_info = session.get_positions(category="linear", symbol=symbol)
        if position_info['result']['list']:
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Error in check_position_exists: {str(e)}")
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

async def process_signal(symbol, qty, action, entry_price):
    try:
        # Retrieve the current position for the symbol
        position_info = session.get_positions(category="linear", symbol=symbol)
        current_position = None
        if position_info['result']['list']:
            current_position = position_info['result']['list'][0]['side']
        logger.info(f"Current position for {symbol}: {current_position}")

        if current_position is None or current_position == "":
            if action == "sell":
                logger.info(f"Opening new Sell position for {symbol}")
                open_position('Sell', symbol, qty)
            elif action == "buy":
                logger.info(f"Opening new Buy position for {symbol}")
                open_position('Buy', symbol, qty)
        elif current_position == "Buy":
            if action == "sell":
                logger.info(f"Closing Buy position and opening Sell position for {symbol}")
                close_position(symbol, qty)
                open_position('Sell', symbol, qty)
        elif current_position == "Sell":
            if action == "buy":
                logger.info(f"Closing Sell position and opening Buy position for {symbol}")
                close_position(symbol, qty)
                open_position('Buy', symbol, qty)
    except Exception as e:
        logger.error(f"Error in process_signal: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)