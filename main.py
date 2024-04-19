import asyncio
import json
import logging
import math

from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP

current_buy_price = None

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

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
        action = body.get("action")

        if action not in ['buy', 'sell']:
            return {"status": "ignored", "reason": f"Invalid action: {action}"}

        logger.info(f"Received {action} action for {symbol}")

        await process_signal(symbol, action)
        return {"status": "success", "data": "Position updated"}

    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format in the alert message: {str(e)}")
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        logger.error(f"Error in handle_webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def get_wallet_balance(symbol):
    try:
        wallet_balance = session.get_wallet_balance(
            category="spot",
            accountType="UNIFIED"
        )
        if wallet_balance['result']:
            coin_list = wallet_balance['result']['list'][0]['coin']
            for coin in coin_list:
                if coin['coin'] == symbol:
                    usdt_wallet_balance = coin['walletBalance']
                    return float(usdt_wallet_balance)
        return 0.0

    except Exception as e:
        logger.error(f"Error in get_wallet_balance: {str(e)}")
        raise

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
        ticker = session.get_tickers(category="spot", symbol=symbol)
        if ticker['result']:
            last_price = float(ticker['result']['list'][0]['lastPrice'])
            return last_price
        else:
            raise Exception(f"Failed to retrieve current price for {symbol}")
    except Exception as e:
        logger.error(f"Error in get_current_price: {str(e)}")
        raise

def open_position(symbol, amount):
    global current_buy_price
    try:
        session.place_order(
            category="spot", symbol=symbol, side='buy', orderType="Market", qty=amount)
        current_buy_price = get_current_price(symbol)
    except Exception as e:
        logger.error(f"Error in open_position: {str(e)}")
        raise

def close_position(symbol, amount):
    global current_buy_price
    try:
        session.place_order(
            category="spot", symbol=symbol, side='sell', orderType="Market", qty=amount)
        current_buy_price = None
    except Exception as e:
        logger.error(f"Error in open_position: {str(e)}")
        raise

async def process_signal(symbol, action):
    global current_buy_price
    try:
        if action == "buy":
            # Get the available USDT balance
            usdt_balance = get_wallet_balance("USDT")

            if usdt_balance > 0:
                rounded_down = math.floor(usdt_balance)
                open_position(symbol, rounded_down)
                current_buy_price = get_current_price(symbol)  # Update the current buy price
            else:
                logger.info(f"Insufficient USDT balance to open a Buy position for {symbol}")

        elif action == "sell":
            # Get the current position quantity of the symbol
            symbol_balance = get_wallet_balance('MYRO')

            if symbol_balance > 0:
                symbol_balance = math.floor(symbol_balance)
                logger.info(f"Closing {symbol} position with quantity: {symbol_balance}")
                close_position(symbol, symbol_balance)
                current_buy_price = None  # Reset the current buy price
            else:
                logger.info(f"No {symbol} position to close")

        else:
            logger.info(f"Invalid action: {action}")

    except Exception as e:
        logger.error(f"Error in process_signal: {str(e)}")
        raise

async def check_price():
    global current_buy_price
    while True:
        if current_buy_price is not None:
            current_price = get_current_price("MYROUSDT")
            price_change_percent = (current_price - current_buy_price) / current_buy_price * 100
            logger.info(f"Current buy price: {current_buy_price}, Current price: {current_price}, Price change: {price_change_percent:.2f}%")
            if price_change_percent >= 0.8:
                logger.info(f"Price increased by {price_change_percent:.2f}%. Selling MYRO.")
                symbol_balance = get_wallet_balance('MYRO')
                if symbol_balance > 0:
                    symbol_balance = math.floor(symbol_balance)
                    close_position("MYROUSDT", symbol_balance)
                    current_buy_price = None  # Reset the current buy price
        await asyncio.sleep(2)  # Check price every 5 seconds

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_price())

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)