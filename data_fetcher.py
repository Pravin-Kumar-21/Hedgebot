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
        return {"BTC": {"latest": {}, "history": []}, "ETH": {"latest": {}, "history": []}}  # Initialize structure

def update_cache(asset: str, proxy=None):
    asset = asset.upper()
    cached_data = load_cached_data()
    
    # Get new prices
    new_data = {
        "bybit": get_bybit_price(f"{asset}USDT", proxy),
        "deribit": get_deribit_price(f"{asset}-PERPETUAL", proxy),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    }

    # Skip if all APIs failed
    if all(v is None for k, v in new_data.items() if k != "timestamp"):
        logger.warning(f"All APIs failed for {asset}. Using cached data.")
        return cached_data

    # Initialize asset structure if missing
    if asset not in cached_data:
        cached_data[asset] = {"latest": {}, "history": []}
    # Convert old format to new format if needed
    elif "latest" not in cached_data[asset]:
        cached_data[asset] = {
            "latest": cached_data[asset],  # Move old data to latest
            "history": []
        }

    # Archive previous "latest" to history (if exists and not empty)
    if cached_data[asset]["latest"]:  # Now safe to access
        cached_data[asset]["history"].append(cached_data[asset]["latest"])

    # Keep last 1000 historical records
    cached_data[asset]["history"] = cached_data[asset]["history"][-1000:]

    # Update latest data
    cached_data[asset]["latest"] = new_data

    # Save to file
    try:
        with open(CACHE_PATH, "w") as f:
            json.dump(cached_data, f, indent=2)
        logger.info(f"Updated {asset} data successfully")
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")

    return cached_data
if __name__ == "__main__":
    # Uncomment and set your proxy if needed
    # proxy = "http://your-proxy-address:port"
    proxy = None
    
    data = update_cache(asset="ETH",proxy=proxy)
    if data:
        print(json.dumps(data, indent=2))
    else:
        print("Failed to fetch data and no cache available.")