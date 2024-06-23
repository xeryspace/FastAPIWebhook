import logging
import asyncio
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

async def place_entry_order_with_sl(trading_pair, side, quantity, price, stop_loss):
    order_params = {
        "category": "linear",
        "symbol": trading_pair,
        "side": side,
        "orderType": "Limit",
        "qty": str(quantity),
        "price": str(price),
        "timeInForce": "PostOnly",
        "reduceOnly": False,
        "closeOnTrigger": False,
        "stopLoss": str(stop_loss),
        "slTriggerBy": "LastPrice",
        "slOrderType": "Market",
        "tpslMode": "Full"
    }
    response = session.place_order(**order_params)
    logger.info(f"Entry order response: {response}")
    return response['result']['orderId'] if 'result' in response else None

async def place_tp_limit_order(trading_pair, side, quantity, price):
    order_params = {
        "category": "linear",
        "symbol": trading_pair,
        "side": side,
        "orderType": "Limit",
        "qty": str(quantity),
        "price": str(price),
        "timeInForce": "PostOnly",
        "reduceOnly": True,
        "closeOnTrigger": True
    }
    response = session.place_order(**order_params)
    logger.info(f"TP order response: {response}")
    return response['result']['orderId'] if 'result' in response else None

async def check_order_status(order_id, trading_pair):
    try:
        response = session.get_order_history(category="linear", symbol=trading_pair, orderId=order_id)
        if 'result' in response and 'list' in response['result']:
            for order in response['result']['list']:
                if order['orderId'] == order_id:
                    return order['orderStatus'] == 'Filled'
        return False
    except Exception as e:
        logger.error(f"Error checking order status: {str(e)}")
        return False

async def cancel_order(order_id, trading_pair):
    try:
        response = session.cancel_order(category="linear", symbol=trading_pair, orderId=order_id)
        logger.info(f"Cancel order response: {response}")
        return True
    except Exception as e:
        logger.error(f"Error cancelling order: {str(e)}")
        return False

@app.post("/trade")
async def trade(request: Request):
    try:
        data = await request.json()
        trading_pair = data.get("trading_pair", "ETHUSDT").upper()
        stop_loss = float(data.get("stop_loss"))
        take_profit = float(data.get("take_profit")) if data.get("take_profit") else None
        amount_to_risk_percentage = float(data.get("amount_to_risk", 1))
        chain_winners = data.get("chain_winners", True)

        # Get account balance
        account_info = session.get_wallet_balance(accountType="UNIFIED")
        if 'result' not in account_info:
            raise HTTPException(status_code=500,
                                detail=f"Error fetching account info: {account_info.get('retMsg', 'Unknown error')}")
        account_balance = float(account_info['result']['list'][0]['totalEquity'])

        # Calculate amount to risk
        amount_to_risk = account_balance * (amount_to_risk_percentage / 100)

        # Get current price
        ticker = session.get_tickers(category="linear", symbol=trading_pair)
        if 'result' not in ticker or 'list' not in ticker['result']:
            raise HTTPException(status_code=500,
                                detail=f"Error fetching current price: {ticker.get('retMsg', 'Unknown error')}")
        current_price = float(ticker['result']['list'][0]['lastPrice'])

        # Determine position side
        position_side = "Buy" if stop_loss < current_price else "Sell"

        # Calculate take profit if not provided (2R)
        if not take_profit:
            risk = abs(current_price - stop_loss)
            take_profit = current_price - (2 * risk) if position_side == "Sell" else current_price + (2 * risk)

        # Adjust risk if chain_winners is True
        chain_status = "Not in a chain"
        if chain_winners:
            closed_pnl = session.get_closed_pnl(category="linear", symbol=trading_pair, limit=6)
            if 'result' in closed_pnl and 'list' in closed_pnl['result']:
                trade_list = closed_pnl['result']['list']
                filtered_trades = []

                for trade in trade_list:
                    pnl = float(trade['closedPnl'])
                    if pnl <= 0:
                        break
                    filtered_trades.append(pnl)

                if len(filtered_trades) % 2 == 0:
                    chain_status = "Chain finished"
                else:
                    if filtered_trades:
                        amount_to_risk += filtered_trades[0]
                        chain_status = f"In a chain, added {filtered_trades[0]} to risk"
            else:
                logger.warning(f"Failed to retrieve closed PnL for {trading_pair}")

        # Calculate quantity
        quantity = round(amount_to_risk / abs(current_price - stop_loss))

        # Adjust entry price slightly for better limit order execution
        entry_price = current_price * 1.0001 if position_side == "Sell" else current_price * 0.9999

        # Place entry limit order with integrated Stop Loss
        entry_order_id = await place_entry_order_with_sl(trading_pair, position_side, quantity, entry_price, stop_loss)
        if not entry_order_id:
            raise HTTPException(status_code=500, detail="Failed to place entry limit order with Stop Loss")

        logger.info(f"Entry order placed with ID: {entry_order_id}")

        # Wait for the entry order to be filled (max 300 seconds)
        order_filled = False
        for i in range(300):
            if await check_order_status(entry_order_id, trading_pair):
                logger.info("Entry order filled")
                order_filled = True
                break
            if i % 5 == 0:
                logger.info(f"Waiting for entry order to fill... Time elapsed: {i} seconds")
            await asyncio.sleep(1)

        if not order_filled:
            logger.warning("Entry order not filled within 300 seconds. Cancelling order.")
            cancel_success = await cancel_order(entry_order_id, trading_pair)
            if cancel_success:
                return {
                    "status": "cancelled",
                    "message": f"Entry order for {trading_pair} was not filled within 300 seconds and has been cancelled."
                }
            else:
                return {
                    "status": "warning",
                    "message": f"Entry order for {trading_pair} was not filled within 300 seconds. Attempted to cancel but encountered an error."
                }

        # Place Take Profit as a limit order
        tp_side = "Sell" if position_side == "Buy" else "Buy"
        tp_order_id = await place_tp_limit_order(trading_pair, tp_side, quantity, take_profit)
        if not tp_order_id:
            logger.error("Failed to place Take Profit limit order")
            raise HTTPException(status_code=500, detail="Failed to place Take Profit limit order")

        # Calculate fees (maker fees for entry and TP, assume taker fee for SL)
        maker_fee_rate = 0.02 / 100  # 0.02%
        taker_fee_rate = 0.055 / 100  # 0.055%
        opening_fee = quantity * entry_price * maker_fee_rate
        closing_fee_sl = quantity * stop_loss * taker_fee_rate
        closing_fee_tp = quantity * take_profit * maker_fee_rate

        # Calculate PnL
        if position_side == "Buy":
            pnl_at_tp = (take_profit - entry_price) * quantity - opening_fee - closing_fee_tp
            pnl_at_sl = (stop_loss - entry_price) * quantity - opening_fee - closing_fee_sl
        else:  # Sell
            pnl_at_tp = (entry_price - take_profit) * quantity - opening_fee - closing_fee_tp
            pnl_at_sl = (entry_price - stop_loss) * quantity - opening_fee - closing_fee_sl

        # Log trade details
        logger.info(f"""
        Trade Details:
        --------------
        Trading Pair: {trading_pair}
        Position Side: {position_side}
        Quantity: {quantity}
        Entry Price: {entry_price}
        Stop Loss: {stop_loss}
        Take Profit: {take_profit}

        Order IDs:
        ----------
        Entry Order ID: {entry_order_id}
        Take Profit Order ID: {tp_order_id}

        Fees:
        -----
        Opening Fee: {opening_fee:.8f}
        Closing Fee (SL): {closing_fee_sl:.8f}
        Closing Fee (TP): {closing_fee_tp:.8f}

        Expected PnL:
        -------------
        PnL if Stopped Out: {pnl_at_sl:.8f}
        PnL if Take Profit Hit: {pnl_at_tp:.8f}

        Chain Status: {chain_status}
        """)

        return {
            "status": "success",
            "message": f"Orders placed for {trading_pair} with Entry (including SL) and Take Profit",
            "entry_order_id": entry_order_id,
            "tp_order_id": tp_order_id
        }

    except Exception as e:
        error_message = str(e)
        if hasattr(e, 'response'):
            error_message += f"\nResponse: {e.response.text}"
        logger.error(f"ERROR - Error in trade: {error_message}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {error_message}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)