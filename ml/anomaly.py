import numpy as np
from collections import defaultdict

def detect_anomalies(transactions: list) -> list:
    """
    Flags transactions that are unusually high for their category.
    Uses Z-score method. Requires at least 3 transactions per category.
    Returns list of transaction ids that are anomalous.
    """
    if not transactions or len(transactions) < 3:
        return []

    category_amounts = defaultdict(list)
    category_ids = defaultdict(list)

    for t in transactions:
        cat = t.get("category", "Others")
        amt = t.get("amount", 0)
        tid = t.get("id")
        if amt and amt > 0:
            category_amounts[cat].append(amt)
            category_ids[cat].append(tid)

    anomalous_ids = []

    for cat, amounts in category_amounts.items():
        if len(amounts) < 3:
            continue
        arr = np.array(amounts)
        mean = np.mean(arr)
        std = np.std(arr)
        if std == 0:
            continue
        for i, amt in enumerate(amounts):
            z_score = abs((amt - mean) / std)
            if z_score > 2.0:
                anomalous_ids.append(category_ids[cat][i])

    return anomalous_ids


def suggest_category(merchant: str) -> str:
    """
    Suggests a category based on merchant name using keyword matching.
    """
    if not merchant:
        return "Others"

    merchant_lower = merchant.lower()

    rules = {
        "Food": [
            "swiggy", "zomato", "dominos", "pizza", "burger", "kfc",
            "mcdonalds", "subway", "cafe", "restaurant", "food", "biryani",
            "hotel", "dhaba", "eat", "kitchen", "bakery", "chai", "coffee",
            "starbucks", "dunkin", "barbeque", "bbq", "mess", "canteen"
        ],
        "Shopping": [
            "amazon", "flipkart", "myntra", "ajio", "nykaa", "meesho",
            "snapdeal", "reliance", "dmart", "bigbasket", "blinkit",
            "zepto", "instamart", "mall", "store", "shop", "mart",
            "fashion", "clothing", "wear", "apparel"
        ],
        "Transport": [
            "ola", "uber", "rapido", "auto", "cab", "taxi", "metro",
            "bus", "train", "irctc", "petrol", "diesel", "fuel",
            "parking", "toll", "redbus", "makemytrip", "indigo",
            "air india", "spicejet", "go air", "flight"
        ],
        "Entertainment": [
            "netflix", "prime", "hotstar", "spotify", "youtube",
            "bookmyshow", "pvr", "inox", "cinema", "movie", "game",
            "gaming", "playstation", "xbox", "steam", "disney"
        ],
        "Utilities": [
            "electricity", "water", "gas", "internet", "broadband",
            "jio", "airtel", "vi ", "vodafone", "bsnl", "bill",
            "recharge", "utility", "maintenance", "rent", "society"
        ],
        "Healthcare": [
            "pharmacy", "hospital", "clinic", "doctor", "medical",
            "apollo", "fortis", "medplus", "1mg", "pharmeasy",
            "medicine", "health", "diagnostic", "lab", "test"
        ]
    }

    for category, keywords in rules.items():
        for keyword in keywords:
            if keyword in merchant_lower:
                return category

    return "Others"