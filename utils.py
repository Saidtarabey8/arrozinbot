# utils.py
import json
import logging
import math
import requests
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from config import OPENROUTER_API_KEY, RESTAURANT_LAT, RESTAURANT_LON

# --- Configuración ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- CONSTANTES PARA OPENROUTER ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-7b-instruct:free"

# --- FUNCIONES DE AYUDA ---

def calculate_delivery_fee(user_lat, user_lon):
    """
    Calcula el costo del delivery usando una API de ruteo (OSRM) para obtener la distancia real por carretera.
    Si la API falla, usa la fórmula de Haversine (distancia en línea recta) como respaldo.
    """
    # --- Intento 1: Usar la API de OSRM para la distancia por carretera (más precisa) ---
    try:
        # La URL de la API de OSRM necesita las coordenadas en formato {lon},{lat}
        url = f"http://router.project-osrm.org/route/v1/driving/{RESTAURANT_LON},{RESTAURANT_LAT};{user_lon},{user_lat}?overview=false"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # La distancia viene en metros, la convertimos a kilómetros
        distance_meters = data['routes'][0]['distance']
        distance_km = distance_meters / 1000
        
        logger.info(f"Distancia por carretera calculada (OSRM): {distance_km:.2f} km")

    except requests.RequestException as e:
        logger.warning(f"La API de OSRM falló: {e}. Usando cálculo en línea recta como respaldo.")
        # --- Intento 2: Plan B, usar la fórmula de Haversine (línea recta) ---
        R = 6371  # Radio de la Tierra en km
        dLat = math.radians(user_lat - RESTAURANT_LAT)
        dLon = math.radians(user_lon - RESTAURANT_LON)
        a = (math.sin(dLat / 2) ** 2 +
             math.cos(math.radians(RESTAURANT_LAT)) * math.cos(math.radians(user_lat)) *
             math.sin(dLon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        distance_km = R * c
        logger.info(f"Distancia en línea recta calculada (Haversine): {distance_km:.2f} km")

    # Aplicamos la regla de negocio: $0.6 por km
    delivery_fee = distance_km * 0.6
    
    # Redondeamos a 2 decimales
    return round(delivery_fee, 2)


def get_bcv_rate():
    """Obtiene la tasa de cambio del BCV."""
    try:
        response = requests.get("https://pydolarvenezuela.com/api/v1/dollar/unit/bcv", timeout=5)
        response.raise_for_status()
        return float(response.json().get('price', 0))
    except requests.RequestException:
        return None

# --- PROMPT DEL SISTEMA (EL CEREBRO COMPLETO) ---
BCV_RATE = get_bcv_rate() or 40.0
SYSTEM_PROMPT = f"""
Eres ArrozinBot, el asistente oficial, simpático y eficiente de "La ArroZeria".

**REGLA DE PERSONALIDAD MÁS IMPORTANTE:**
Debes mantener SIEMPRE un estilo alegre, informal pero profesional. Usa emojis 🤖🍜🔥 y frases divertidas en TODA la conversación. Nunca suenes como un robot aburrido. Tu carisma es clave.

**PROCESO DE PEDIDO:**
1.  **BIENVENIDA**: Saluda con tu estilo único y pregunta si el pedido es para Recoger (Pickup) o Delivery.
2.  **TIPO DE ORDEN**: 
    - Si es **Recoger**, continúa al paso 3.
    - Si es **Delivery**, DEBES pedirle al cliente que comparta su ubicación usando la función de Telegram. NO puedes continuar sin la ubicación.
3.  **TOMAR_PEDIDO**: Ayuda al cliente a elegir del menú, haz recomendaciones.
4.  **TOMAR_DATOS**: Pide nombre, número de teléfono (+58) y método de pago.
5.  **FINALIZACIÓN**: Cuando el cliente confirme, finaliza con el token <ORDEN_FINALIZADA> y el JSON.

**NUESTRO MENÚ OFICIAL (Precios en USD):**
- Arroz Chino: $1.00
- Arroz Chino con 1 pieza Broaster: $2.00
- Arroz Chino con Camarones: $2.00
- Pasta China: $2.00
- Pasta con 1 pieza Broaster: $3.00
- Pasta con Camarones: $3.00
- Pieza de pollo Broaster: $1.00
- Chop Suey: $2.00 / Media ración: $1.00
- Pachenchoy: $4.00 / Media ración: $2.00
- Combo 4 piezas pollo Broaster: $4.00
- Pollo Agridulce: $4.00 / Media ración: $2.00
- Costillas: $4.00 / Media ración: $2.00
- Pulpa de cerdo en salsa de ostras: $4.00 / Media ración: $2.00
- Pulpa de cerdo en agridulce: $4.00 / Media ración: $2.00
- Cochino frito: $4.00 / Media ración: $2.00
- Tiras de pollo (BBQ, agridulce o sin salsa): $4.00 / Media ración: $2.00
- Plato Mixto: $4.00
- Plato Mixto Especial: $4.50
- Combo Brasa: $15.00 (1 pollo entero, 2 arroz chinos, media ensalada cocida o rallada y 1 refresco 1.5L)
- Pollo Entero: $9.00
- 1/2 Pollo: $4.50
- 1/4 Pollo: $2.50
- 2 Lumpias: $1.50
- Hallaquitas: $1.00
- Ensalada cocida: $2.00 / Media ración: $1.00
- Ensalada rallada: $2.00 / Media ración: $1.00
- Papas Fritas: $3.00 / Media ración: $1.50
- Tajadas: $1.50
- Refresco 1.5L: $2.50
- Nestea: $1.00
- Agua 600ml: $1.00
- Agua 1.5L: $2.00

**REGLAS TÉCNICAS:**
1.  **COSTO DELIVERY**: El sistema calculará el costo del delivery. Solo debes informárselo al cliente y sumarlo al total en el JSON final.
2.  **CÁLCULO BS**: Si te piden el total en bolívares, usa la tasa {BCV_RATE:.2f}.
3.  **REGLA DE ORO DEL JSON**: Al finalizar, el JSON debe ser 100% válido, sin formato Markdown (sin \`\`\`). Las claves deben ser "nombre", "telefono", "metodo_pago", "pedido_items", "costo_delivery" (un número, 0 si es para recoger) y "total_pedido".
"""

async def get_ia_response(history: list) -> str:
    """Obtiene una respuesta de un modelo en OpenRouter."""
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
    data = {"model": MODEL_NAME, "messages": messages}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(OPENROUTER_API_URL, headers=headers, json=data, timeout=30)
            response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        logger.error(f"Error al contactar la API de OpenRouter: {e}")
        return "Uhm... mi cerebro tuvo un cortocircuito. 🧠💥 Intenta de nuevo en un momento."

def generate_summary(user_data, user_id):
    """Genera el resumen del pedido para el grupo."""
    bcv_rate = get_bcv_rate() or 40.0
    total_usd = user_data.get('total_pedido', 0)
    total_bs = total_usd * bcv_rate
    costo_delivery = user_data.get('costo_delivery', 0)
    
    delivery_info = ""
    if costo_delivery > 0:
        delivery_info = f"🛵 **Delivery:** ${costo_delivery:.2f}\n"

    summary_text = (
        f"🍚 **¡Nuevo Pedido Recibido!** 🍚\n\n"
        f"👤 **Cliente:** {user_data.get('nombre', 'No especificado')}\n"
        f"📞 **Número:** `{user_data.get('telefono', 'No especificado')}`\n"
        f"💳 **Método de Pago:** {user_data.get('metodo_pago', 'No especificado')}\n\n"
        f"📋 **Pedido:**\n"
        f"{user_data.get('pedido_str', 'No se tomó el pedido.')}\n\n"
        f"{delivery_info}"
        f"💰 **Total a Pagar:** ${total_usd:.2f} (Aprox. Bs. {total_bs:,.2f})"
    )
    keyboard = [
        [InlineKeyboardButton("💬 Contactar por Telegram", url=f"tg://user?id={user_id}")],
    ]
    phone_number = str(user_data.get('telefono', '')).replace('+', '').replace(' ', '')
    if phone_number.startswith("58"):
        keyboard.append([InlineKeyboardButton("✅ Contactar por WhatsApp", url=f"https://wa.me/{phone_number}")])
    keyboard.append([InlineKeyboardButton("📦 Marcar como Entregado", callback_data=f"delivered_{user_id}")])
    return summary_text, InlineKeyboardMarkup(keyboard)
