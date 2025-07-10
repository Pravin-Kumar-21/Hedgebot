import requests
import json
import os
from datetime import datetime
from logger import get_logger

logger = get_logger()

CACHE_PATH = "cache/live_data.json"

# Create cache folder if not exists
os.makedirs("cache", exist_ok=True)

def fetch_with_proxy(url, proxy=None):
    try:
        proxies = {"http": proxy, "https": proxy} if proxy else None
        res = requests.get(url, proxies=proxies, timeout=10)
        res.raise_for_status()  # Raise error for bad status codes
        return res.json()
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None

# def get_okx_price(symbol:str, proxy=None):
#     try:
#         url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
#         data = fetch_with_proxy(url, proxy)
#         return float(data['data'][0]['last']) if data else None
#     except Exception as e:
#         logger.error(f"OKX fetch error: {e}")
#         return None

def get_bybit_price(symbol:str, proxy=None):
    try:
        url = "https://api.bybit.com/v5/market/tickers?category=linear"
        data = fetch_with_proxy(url, proxy)
        if data:
            for item in data["result"]["list"]:
                if item["symbol"] == symbol:
                    return float(item["lastPrice"])
        return None
    except Exception as e:
        logger.error(f"Bybit fetch error: {e}")
        return None

def get_deribit_price(symbol="BTC-PERPETUAL", proxy=None):
    try:
        url = f"https://www.deribit.com/api/v2/public/ticker?instrument_name={symbol}"
        data = fetch_with_proxy(url, proxy)
        return float(data["result"]["last_price"]) if data else None
    except Exception as e:
        logger.error(f"Deribit fetch error: {e}")
        return None

# def get_coingecko_price(coin_id="bitcoin"):
#     try:
#         url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
#         data = fetch_with_proxy(url)
#         return float(data[coin_id]["usd"]) if data else None
#     except Exception as e:
#         logger.error(f"CoinGecko fetch error: {e}")
#         return None

def load_cached_data():
    try:
        with open(CACHE_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def update_cache(asset: str, proxy=None):
    asset = asset.upper()  # Normalize asset name like BTC, ETH
    
    try:
        cached_data = load_cached_data() or {}
    except Exception as e:
        logger.error(f"Failed to load cache: {e}")
        cached_data = {}

    # Keep your original live_data structure
    live_data = {
        asset: {
            "bybit": get_bybit_price(symbol=f"{asset}USDT", proxy=proxy),
            "deribit": get_deribit_price(symbol=f"{asset}-PERPETUAL", proxy=proxy),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        }
    }

    # Check if all live fetches failed
    if all(v is None for k, v in live_data[asset].items() if k != "timestamp"):
        logger.warning(f"⚠️ All API requests for {asset} failed. Using existing cache.")
        return cached_data if cached_data else None

    # Merge new live_data into cached_data
    cached_data.update(live_data)

    # Save the updated cache to file
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cached_data, f, indent=2)
        logger.info(f"✅ Cache updated for {asset}")
    except Exception as e:
        logger.error(f"❌ Failed to write cache: {e}")

    return cached_data


if __name__ == "__main__":
    # Uncomment and set your proxy if needed
    # proxy = "http://your-proxy-address:port"
    proxy = None
    
    data = update_cache(proxy=proxy)
    if data:
        print(json.dumps(data, indent=2))
    else:
        print("Failed to fetch data and no cache available.")