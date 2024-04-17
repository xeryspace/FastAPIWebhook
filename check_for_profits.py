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
    symbols = ['FETUSDT', '1000BONKUSDT', 'WIFUSDT', '1000PEPEUSDT']  # Add the symbols you want to check positions for
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

                    if unrealised_pnl >= 2.0:
                        logger.info(f"Closing the entire position for {symbol} (Profit)")
                        close_position(symbol, size)
                    elif unrealised_pnl <= -2.0:
                        logger.info(f"Closing the entire position for {symbol} (Loss)")
                        close_position(symbol, size)
                else:
                    logger.info(f"No positions found for {symbol}")

        except Exception as e:
            logger.error(f"Error in check_positions: {str(e)}")

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
