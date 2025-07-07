# main.py
# Este archivo inicia la aplicación del bot y registra todos los manejadores.

from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from config import BOT_TOKEN
# Importamos todos los manejadores necesarios
from handlers import start, cancel, master_ai_handler, mark_as_delivered_handler

def main() -> None:
    """
    Inicia el bot y lo mantiene corriendo en modo polling.
    """
    # --- LÍNEA CORREGIDA ---
    # Hacemos la conexión más robusta añadiendo timeouts.
    # Le damos 10 segundos para conectar y 30 segundos para leer una respuesta.
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(10)
        .read_timeout(30)
        .build()
    )

    # --- REGISTRO DE MANEJADORES ---

    # 1. Comandos básicos para iniciar o cancelar
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cancel', cancel))

    # 2. Manejador para los botones (como "Marcar como Entregado")
    application.add_handler(CallbackQueryHandler(mark_as_delivered_handler, pattern='^delivered_'))

    # 3. Manejador principal de la IA para todos los mensajes de texto y ubicaciones
    application.add_handler(MessageHandler(filters.TEXT | filters.LOCATION, master_ai_handler))

    print("🚀 ArrozinBot con OpenRouter está en línea...")
    
    # Inicia el bot para que escuche nuevos mensajes
    application.run_polling()

if __name__ == "__main__":
    main()
