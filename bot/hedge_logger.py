import os
import json
import logging
from datetime import datetime

# Get logger from parent module
logger = logging.getLogger(__name__)

def log_hedge(asset: str, size: float, price: float , mode="manual"):
    """
    Log hedge operations to a JSON history file
    
    Args:
        asset (str): The asset being hedged
        size (float): Position size
        price (float): Reference price at time of hedge
    """
    try:
        # Create cache directory if needed
        BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # Goes up from utils/ to hedgebot/
        CACHE_DIR = os.path.join(BASE_DIR, "cache")
        HEDGE_HISTORY_FILE = os.path.join(CACHE_DIR, "hedge_history.json")
        
        # Create record with timestamp
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",  # ISO format with UTC marker
            "asset": asset.upper(),
            "size": size,
            "price": price,
            "mode": mode
        }
        
        # Load existing history or create new list
        history = []
        if os.path.exists(HEDGE_HISTORY_FILE):
            try:
                with open(HEDGE_HISTORY_FILE, "r") as f:
                    history = json.load(f)
                # Ensure we have a list
                if not isinstance(history, list):
                    logger.warning("Hedge history was not a list, resetting")
                    history = []
            except json.JSONDecodeError:
                logger.error("Failed to parse hedge history, resetting")
                history = []
        
        # Append new record
        history.append(record)
        
        # Save with pretty-printing
        with open(HEDGE_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
            
        logger.info(f"Logged hedge: {asset} {size} @ {price} ({mode})")
        
    except Exception as e:
        logger.error(f"Failed to write hedge history: {str(e)}", exc_info=True)