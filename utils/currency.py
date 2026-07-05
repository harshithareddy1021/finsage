import requests

FALLBACK_RATE = 84.0  # INR per USD fallback

def get_usd_to_inr_rate():
    try:
        response = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=3
        )
        data = response.json()
        return data["rates"]["INR"]
    except Exception:
        return FALLBACK_RATE

def convert_to_inr(amount, currency, rate):
    if currency == "USD":
        return round(amount * rate, 2)
    return amount

def format_inr(amount):
    return f"₹{amount:,.2f}"