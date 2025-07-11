import pandas as pd
from data_fetcher import load_cached_data

def compute_correlation(asset="BTC", window=24):
    data = load_cached_data()

    # Validate data presence
    if asset not in data or not data[asset]["history"]:
        return None, None

    # Load historical entries
    entries = data[asset]["history"]
    df = pd.DataFrame(entries)

    # Validate necessary fields
    if 'timestamp' not in df or 'bybit' not in df or 'deribit' not in df:
        return None, None

    # Convert timestamp and sort
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.set_index('timestamp').sort_index()

    # Drop rows with missing price data
    df = df[['bybit', 'deribit']].dropna()

    # Ensure enough data for correlation window
    if len(df) < window:
        return None, df  # Not enough data for rolling correlation

    # Compute rolling Pearson correlation
    df['rolling_corr'] = df['bybit'].rolling(window=window).corr(df['deribit'])

    # Extract latest correlation value
    latest_corr = df['rolling_corr'].iloc[-1] if not df['rolling_corr'].isnull().all() else None

    return latest_corr, df.tail(30)  # Return latest value and last 30 points for plotting/debug
