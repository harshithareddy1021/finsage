import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def validate_keys():
    if not GROQ_API_KEY:
        raise ValueError("Missing GROQ_API_KEY in .env file")

validate_keys()