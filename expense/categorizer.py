def categorize_transaction(merchant):

    merchant = merchant.lower()

    if "google" in merchant:
        return "Entertainment"

    if "swiggy" in merchant or "zomato" in merchant:
        return "Food"

    if "restaurant" in merchant or "hotel" in merchant:
        return "Food"

    if "amazon" in merchant or "flipkart" in merchant:
        return "Shopping"

    return "Others"