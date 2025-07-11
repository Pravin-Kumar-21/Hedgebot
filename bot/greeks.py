def calculate_greeks(spot_price, strike_price, time_to_expiry_days, volatility, risk_free_rate=0.05, option_type="call"):
    import math
    from scipy.stats import norm

    try:
        S = float(spot_price)
        K = float(strike_price)
        T = float(time_to_expiry_days) / 365.0
        sigma = float(volatility)
        r = float(risk_free_rate)
        option_type = option_type.lower()
    except (TypeError, ValueError) as e:
        return {"error": f"Invalid input type: {str(e)}"}

    if T <= 0:
        return {"error": f"Invalid time to expiry: {time_to_expiry_days} days"}
    if sigma <= 0:
        return {"error": f"Volatility must be positive: {volatility}"}
    if S <= 0 or K <= 0:
        return {"error": "Spot and Strike price must be positive"}
    if option_type not in ["call", "put"]:
        return {"error": f"Invalid option type: {option_type}"}

    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        pdf_d1 = norm.pdf(d1)
        cdf_d1 = norm.cdf(d1)
        cdf_d2 = norm.cdf(d2)
        cdf_neg_d1 = norm.cdf(-d1)
        cdf_neg_d2 = norm.cdf(-d2)

        if option_type == "call":
            delta = cdf_d1
            price = S * cdf_d1 - K * math.exp(-r * T) * cdf_d2
            theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * cdf_d2) / 365
        else:
            delta = -cdf_neg_d1
            price = K * math.exp(-r * T) * cdf_neg_d2 - S * cdf_neg_d1
            theta = (-S * pdf_d1 * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * cdf_neg_d2) / 365

        gamma = pdf_d1 / (S * sigma * math.sqrt(T))
        vega = S * pdf_d1 * math.sqrt(T) / 100

        return {
            "price": round(price, 2),
            "delta": round(delta, 4),
            "gamma": round(gamma, 4),
            "theta": round(theta, 4),
            "vega": round(vega, 4)
        }

    except Exception as e:
        return {"error": f"Calculation error: {str(e)}"}
