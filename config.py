# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- Coordenadas del restaurante ---
RESTAURANT_LAT = float(os.getenv("RESTAURANT_LAT", "0.0"))
RESTAURANT_LON = float(os.getenv("RESTAURANT_LON", "0.0"))

# Valida que todas las claves necesarias estén definidas
if not all([BOT_TOKEN, GROUP_CHAT_ID, OPENROUTER_API_KEY, RESTAURANT_LAT, RESTAURANT_LON]):
    raise ValueError("Error: Asegúrate de definir todas las claves en tu archivo .env, incluyendo RESTAURANT_LAT y RESTAURANT_LON")
