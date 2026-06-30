
import base64
import json
import re
from groq import Groq
from utils.helpers import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

def image_to_base64(image):
    import io
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")

def extract_text_from_image(image):
    image_data = image_to_base64(image)
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "Extract all visible text from this payment screenshot."
                    }
                ]
            }
        ],
        max_tokens=500
    )
    return response.choices[0].message.content

def extract_transaction_from_image(image):
    image_data = image_to_base64(image)

    prompt = """Analyze this payment screenshot and extract transaction details.
Return ONLY a valid JSON object with exactly these fields:
{
    "amount": <number only, no currency symbol>,
    "merchant": <merchant or app name as string>,
    "date": <date as string>,
    "category": <one of: Food, Shopping, Transport, Entertainment, Utilities, Healthcare, Others>,
    "payment_method": <one of: UPI, Credit Card, Debit Card, Net Banking, Cash, Unknown>
}
If any field cannot be determined use null.
Return only the JSON object, no explanation, no markdown."""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        max_tokens=300
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"```json|```", "", raw).strip()

    try:
        data = json.loads(raw)
        required = ["amount", "merchant", "date", "category", "payment_method"]
        for field in required:
            if field not in data:
                data[field] = None
        return data
    except json.JSONDecodeError:
        return {
            "amount": None,
            "merchant": None,
            "date": None,
            "category": "Others",
            "payment_method": "Unknown"
        }