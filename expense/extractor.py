import re


def words_to_number(words):
    number_dict = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "hundred": 100, "thousand": 1000
    }

    words = words.lower().split()
    total = 0
    current = 0

    for word in words:
        if word not in number_dict:
            continue

        value = number_dict[word]

        if value == 100:
            current *= 100
        elif value == 1000:
            current *= 1000
            total += current
            current = 0
        else:
            current += value

    total += current
    return total


def extract_amount(text):

    words_match = re.search(r'Rupees (.*?) Only', text, re.IGNORECASE)
    if words_match:
        return words_to_number(words_match.group(1))

    total_match = re.search(r'TOTAL[^\d]*([\d,]+\.\d{2})', text, re.IGNORECASE)
    if total_match:
        return float(total_match.group(1).replace(",", ""))

    numbers = re.findall(r'\d+\.\d{2}', text)
    if numbers:
        cleaned = [float(num.replace(",", "")) for num in numbers]
        return max(cleaned)

    return None


def extract_merchant(text):

    lines = text.split("\n")

    for line in lines[:3]:
        if len(line.strip()) > 3:
            return line.strip()

    return "Unknown"


def extract_date(text):

    match = re.search(r'\d{1,2}/\d{1,2}/\d{4}', text)
    if match:
        return match.group()

    match = re.search(r'\d{1,2}\s[A-Za-z]{3}\s\d{4}', text)
    if match:
        return match.group()

    return "Unknown"


def extract_payment_method(text):

    match = re.search(
        r'(Debit Card|Credit Card|UPI|Net Banking|Cash)',
        text,
        re.IGNORECASE
    )

    if match:
        return match.group()

    return "Unknown"


def extract_transaction(text):

    return {
        "amount": extract_amount(text),
        "merchant": extract_merchant(text),
        "date": extract_date(text),
        "payment_method": extract_payment_method(text)
    }