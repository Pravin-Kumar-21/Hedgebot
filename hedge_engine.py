import logging
from datetime import datetime
import random

logger = logging.getLogger(__name__)

def execute_hedge(asset: str, size: float, price: float):
    logger.info(f"Executing hedge for {asset}: size={size}, price={price}")
    
    slippage_pct = random.uniform(-0.2, 0.2)
    execution_price = price * (1 + slippage_pct / 100)

    txn_cost = execution_price * size * 0.00075
    timestamp = datetime.utcnow().isoformat()

    return {
        "asset": asset,
        "size": size,
        "original_price": round(price, 2),
        "execution_price": round(execution_price, 2),
        "slippage_pct": round(slippage_pct, 4),
        "cost": round(txn_cost, 2),
        "timestamp": timestamp
    }
