import time
import logging
from pybit.unified_trading import HTTP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

api_key = 'ULI4j96SQhGePVhxCu'
api_secret = 'XnBhumm73kDKJSFDFLKEZSLkkX2KwMvAj4qC'
session = HTTP(testnet=False, api_key=api_key, api_secret=api_secret)

def check_positions():
    symbols = ['MYROUSDT', 'NEARUSDT', 'SOLUSDT', 'ONGUSDT']  # Add the symbols you want to check positions for
    processed_positions = {}  # Keep track of processed positions
    while True:
        time.sleep(2)  # Check positions every 2 seconds
        try:
            for symbol in symbols:
                positions = session.get_positions(category="linear", symbol=symbol)['result']['list']

                if positions:
                    position = positions[0]  # Get the first position for the symbol
                    symbol = position['symbol']

                    if 'unrealisedPnl' not in position or position['unrealisedPnl'] == '':
                        continue

                    unrealised_pnl = float(position['unrealisedPnl'])

                    if 'size' in position and position['size'] != '':
                        size = float(position['size'])
                    else:
                        continue

                    if symbol not in processed_positions or size != processed_positions[symbol]:
                        if unrealised_pnl >= 0.5:
                            logger.info(f"Taking 50% profit and setting trailing stop loss for {symbol}")
                            take_partial_profit(symbol, size, 0.5)  # Take 50% profit
                            set_trailing_stop_loss(symbol, 0.4)  # Set trailing stop loss to 2% below current price
                            processed_positions[symbol] = size  # Store the processed position size
                else:
                    logger.info(f"No positions found for {symbol}")

        except Exception as e:
            logger.error(f"Error in check_positions: {str(e)}")

def take_partial_profit(symbol, qty, profit_percent):
    try:
        position_info = session.get_positions(category="linear", symbol=symbol)
        if position_info['result']['list']:
            side = "Buy" if position_info['result']['list'][0]['side'] == "Sell" else "Sell"
            qty_to_close = qty * profit_percent
            session.place_order(
                category="linear", symbol=symbol, side=side, orderType="Market", qty=qty_to_close)
    except Exception as e:
        logger.error(f"Error in take_partial_profit: {str(e)}")

def set_trailing_stop_loss(symbol, trailing_stop_percent=0.005):
    try:
        position_info = session.get_positions(category="linear", symbol=symbol)
        if position_info['result']['list']:
            position = position_info['result']['list'][0]
            if 'avgPrice' in position and position['avgPrice'] != '':
                session.set_trading_stop(
                    category="linear",
                    symbol=symbol,
                    trailing_stop=str(trailing_stop_percent),
                    trailing_stop_trigger="LastPrice"
                )
            else:
                logger.warning(f"Average price not found for {symbol}")
    except Exception as e:
        logger.error(f"Error in set_trailing_stop_loss: {str(e)}")

def close_position(symbol, qty):
    try:
        position_info = session.get_positions(category="linear", symbol=symbol)
        if position_info['result']['list']:
            side = "Buy" if position_info['result']['list'][0]['side'] == "Sell" else "Sell"
            session.place_order(
                category="linear", symbol=symbol, side=side, orderType="Market", qty=qty)
    except Exception as e:
        logger.error(f"Error in close_position: {str(e)}")


if __name__ == "__main__":
    check_positions()