import math
from scipy.stats import norm
import logging

# Set up logger
logger = logging.getLogger(__name__)

def calculate_greeks(spot_price, strike_price, time_to_expiry_days, volatility, risk_free_rate=0.05, option_type="call"):
    """
    Calculate option Greeks using the Black-Scholes model.
    Returns a dictionary with keys: delta, gamma, theta, vega, or error
    """
    # Validate input types
    try:
        # Convert all inputs to float
        S = float(spot_price)
        K = float(strike_price)
        T = float(time_to_expiry_days) / 365.0  # Convert days to years
        sigma = float(volatility)
        r = float(risk_free_rate)
        option_type = str(option_type).lower()
    except (TypeError, ValueError) as e:
        return {"error": f"Invalid input type: {str(e)}"}

    # Validate input values
    if T <= 0:
        return {"error": f"Invalid time to expiry: {time_to_expiry_days} days"}
    if sigma <= 0:
        return {"error": f"Volatility must be positive: {volatility}"}
    if S <= 0:
        return {"error": f"Spot price must be positive: {spot_price}"}
    if K <= 0:
        return {"error": f"Strike price must be positive: {strike_price}"}
    if option_type not in ["call", "put"]:
        return {"error": f"Invalid option type: {option_type}. Must be 'call' or 'put'"}

    # Log inputs for debugging
    logger.info(f"Calculating Greeks: S={S}, K={K}, T={T}, σ={sigma}, r={r}, type={option_type}")

    try:
        # Black-Scholes calculation
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        # Common factors
        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        cdf_neg_d1 = norm.cdf(-d1)
        cdf_neg_d2 = norm.cdf(-d2)

        # Calculate Greeks based on option type
        if option_type == "call":
            delta = cdf_d1
            theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * cdf_d2) / 365
        else:  # put
            delta = -cdf_neg_d1
            theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * cdf_neg_d2) / 365

        gamma = pdf_d1 / (S * sigma * math.sqrt(T))
        vega = S * pdf_d1 * math.sqrt(T) / 100  # per 1% change in volatility

        return {
            "delta": round(delta, 4),
            "gamma": round(gamma, 4),
            "theta": round(theta, 4),
            "vega": round(vega, 4)
        }

    except Exception as e:
        # Log full exception for debugging
        logger.exception("Error in Greek calculation")
        return {"error": f"Calculation error: {str(e)}"}