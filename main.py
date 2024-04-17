import asyncio
import json
from fastapi import FastAPI, HTTPException, Request
from pybit.unified_trading import HTTP

app = FastAPI()

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

processed_positions = set()

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

        print(f"Received {action} action for {symbol}")

        # Retrieve the current position for the symbol
        position_info = session.get_positions(category="linear", symbol=symbol)
        current_position = None
        if position_info['result']['list']:
            current_position = position_info['result']['list'][0]['side']
            print(f"Current position for {symbol}: {current_position}")
        else:
            print(f"No current position for {symbol}")

        if current_position is None or current_position == "":
            if action == "sell":
                open_position('Sell', symbol, qty)
                print(f'Case 1: Opened a Short for {symbol}')
            elif action == "buy":
                open_position('Buy', symbol, qty)
                print(f'Case 2: Opened a Long for {symbol}')
        elif current_position == "Buy":
            if action == "buy":
                print(f'Case 3: Already in a Long for {symbol}, doing nothing')
            elif action == "sell":
                close_position(symbol, qty)
                print(f'Closed a Long for {symbol}')
                open_position('Sell', symbol, qty)
                print(f'Case 4: Opened a Short for {symbol}')
        elif current_position == "Sell":
            if action == "sell":
                print(f'Case 5: Already in a Short for {symbol}, doing nothing')
            elif action == "buy":
                close_position(symbol, qty)
                print(f'Closed a Short for {symbol}')
                open_position('Buy', symbol, qty)
                print(f'Case 6: Opened a Long for {symbol}')

        return {"status": "success", "data": "Position updated"}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in the alert message")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def open_position(side, symbol, qty):
    session.place_order(
        category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    print(f'Opened a {side} position for {symbol}')

def close_position(symbol, qty):
    position_info = session.get_positions(category="linear", symbol=symbol)
    if position_info['result']['list']:
        side = "Buy" if position_info['result']['list'][0]['side'] == "Sell" else "Sell"
        session.place_order(
            category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
        print(f'Closed a {position_info["result"]["list"][0]["side"]} position for {symbol}')

async def check_positions():
    symbols = ['FETUSDT', '1000BONKUSDT', 'WIFUSDT']  # Add the symbols you want to check positions for
    while True:
        try:
            for symbol in symbols:
                positions = session.get_positions(category="linear", symbol=symbol)['result']['list']

                for position in positions:
                    symbol = position['symbol']
                    position_idx = position['positionIdx']

                    if 'unrealisedPnl' in position and position['unrealisedPnl'] != '':
                        unrealised_pnl = float(position['unrealisedPnl'])
                        unrealised_pnl_rounded = round(unrealised_pnl, 2)
                        print(f"Unrealised PnL for {symbol}: ${unrealised_pnl_rounded}")
                    else:
                        print(f"Unrealised PnL not found or empty for position {position_idx} of symbol {symbol}")
                        continue

                    if 'size' in position and position['size'] != '':
                        size = float(position['size'])
                        print(f"Size for position: {size}")
                    else:
                        print(f"Size not found or empty for position of symbol {symbol}")
                        continue

                    if 'avgPrice' in position and position['avgPrice'] != '':
                        avgPrice = float(position['avgPrice'])
                    else:
                        print(f"Average price not found or empty for position {position_idx} of symbol {symbol}")
                        continue

                    if unrealised_pnl > 3.0 and position_idx not in processed_positions:
                        print(f"Position meets the criteria for taking profit")
                        qty_to_close = size * 0.5
                        print(f"Closing {qty_to_close} units of {symbol}")
                        close_position(symbol, qty_to_close)

                        stop_loss = avgPrice
                        print(f"Moving stop loss to {stop_loss} for {symbol}")
                        update_stop_loss(symbol, stop_loss)

                        processed_positions.add(position_idx)
                        print(f"Added position to the processed set")
                    else:
                        continue

        except Exception as e:
            print(f"Error while checking positions: {str(e)}")

        await asyncio.sleep(15)
        
def update_stop_loss(symbol, stop_loss):
    session.set_trading_stop(
        category="linear",
        symbol=symbol,
        stopLoss=str(stop_loss)
    )
    print(f'Updated stop loss for {symbol} to {stop_loss}')

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(check_positions())

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)