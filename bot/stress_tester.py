from greeks import calculate_greeks  # your own function
from datetime import datetime, timedelta
import math

def simulate_stress_scenarios(asset_name, base_params, scenarios):
    """
    base_params: {
        "spot": 110000,
        "strike": 105000,
        "time_to_expiry": 10 (days),
        "volatility": 0.65,
        "rate": 0.0,
        "option_type": "call"
    }
    """

    results = {}

    for label, shocks in scenarios.items():
        # Apply shocks
        spot = base_params["spot"] * (1 + shocks.get("spot", 0))
        volatility = base_params["volatility"] * (1 + shocks.get("vol", 0))
        days = base_params["time_to_expiry"] - shocks.get("days_passed", 0)
        time_to_expiry = max(days / 365, 0.001)  # avoid division by 0

        # Calculate Greeks and price under stress
        greek_result = calculate_greeks(
            spot,
            base_params["strike"],
            days,  # days to expiry
            volatility,
            base_params.get("rate", 0.05),  # default 5% risk-free rate
            base_params["option_type"]
        )

        results[label] = {
            "spot": spot,
            "volatility": volatility,
            "days_remaining": days,
            **greek_result
        }

    return results
