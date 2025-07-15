# handlers.py
import json
import logging
import re
from telegram import Update
from telegram.ext import ContextTypes
from config import GROUP_CHAT_ID
from utils import get_ia_response, generate_summary, calculate_delivery_fee
from telegram.helpers import escape_markdown

logger = logging.getLogger(__name__)

async def master_ai_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Manejador principal que distingue entre texto y ubicación, y gestiona la conversación con la IA.
    """
    user_id = update.effective_user.id
    history = context.user_data.setdefault('history', [])
    
    if update.message.location:
        location = update.message.location
        fee = calculate_delivery_fee(location.latitude, location.longitude)
        context.user_data['delivery_fee'] = fee
        user_text = (f"El cliente ha compartido su ubicación. El costo del delivery es de ${fee:.2f}. "
                     "Informa al cliente de este costo y ahora pídele su pedido.")
        await update.message.reply_text(f"¡Ubicación recibida! Tu delivery costará ${fee:.2f} 🛵.")
    else:
        user_text = update.message.text

    history.append({'role': 'user', 'content': user_text})

    try:
        await update.message.chat.send_action(action='typing')
        ai_response_text = await get_ia_response(history)
        history.append({'role': 'assistant', 'content': ai_response_text})

        if "<ORDEN_FINALIZADA>" in ai_response_text:
            logger.info(f"IA ha finalizado el pedido. Respuesta completa: {ai_response_text}")
            try:
                # --- LÓGICA DE EXTRACCIÓN MEJORADA ---
                # Buscamos el JSON de forma más robusta, ignorando texto extra.
                text_after_tag = ai_response_text.split('<ORDEN_FINALIZADA>', 1)[1]
                
                start_index = text_after_tag.find('{')
                end_index = text_after_tag.rfind('}')

                if start_index == -1 or end_index == -1:
                    logger.error("No se pudo encontrar un objeto JSON válido en la respuesta de la IA.")
                    await update.message.reply_text(
                        "¡Ay, caramba! Entendí que terminaste, pero los datos del pedido vinieron incompletos. "
                        "Por favor, di **'confirmar pedido'** para intentarlo de nuevo."
                    )
                    return

                json_string = text_after_tag[start_index : end_index + 1]
                logger.info(f"JSON extraído para procesar: {json_string}")

                order_data = json.loads(json_string)
                order_data['costo_delivery'] = context.user_data.get('delivery_fee', 0)
                
                pedido_items_list = order_data.get("pedido_items", [])
                pedido_lines = []
                for item in pedido_items_list:
                    if isinstance(item, dict):
                        line = f"- {item.get('cantidad', 1)}x {item.get('producto', 'Producto no especificado')}"
                        pedido_lines.append(line)
                    elif isinstance(item, str):
                        line = f"- 1x {item}"
                        pedido_lines.append(line)
                order_data['pedido_str'] = "\n".join(pedido_lines)

                summary_text, reply_markup = generate_summary(order_data, user_id)
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=summary_text, reply_markup=reply_markup, parse_mode='Markdown')

                await update.message.reply_text("¡Pedido completado y enviado a la cocina! Gracias por tu compra. 👨‍🍳")
                context.user_data.clear()

            except json.JSONDecodeError as e:
                logger.error(f"Error de decodificación de JSON: {e}. String que se intentó decodificar: '{json_string}'")
                await update.message.reply_text(
                    "¡Ay, caramba! Entendí que terminaste, pero los datos del pedido vinieron con un formato incorrecto. "
                    "Por favor, di **'confirmar pedido'** para intentarlo de nuevo."
                )
                return
            except Exception as e:
                logger.error(f"Error inesperado al procesar la orden finalizada: {e}")
                await update.message.reply_text(
                    "¡Ay, caramba! Hubo un problema inesperado al procesar tu pedido. "
                    "Por favor, di **'confirmar pedido'** para intentarlo de nuevo."
                )
                return
        else:
            await update.message.reply_text(ai_response_text)

    except Exception as e:
        logger.error(f"Error en la sesión de chat con la IA: {e}")
        await update.message.reply_text("Uhm... mi cerebro tuvo un cortocircuito. 🧠💥 Intenta de nuevo en un momento.")


async def mark_as_delivered_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja el clic en el botón 'Marcar como Entregado'."""
    query = update.callback_query
    await query.answer("¡Pedido marcado como entregado!")
    original_text = query.message.text
    new_text = f"✅ *ENTREGADO* ✅\n\n~{original_text}~"
    await query.edit_message_text(text=new_text, parse_mode='MarkdownV2')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando para iniciar o reiniciar la conversación."""
    context.user_data.clear()
    await update.message.reply_text("¡Hola! Soy ArrozinBot. ¡Tu sesión ha sido reiniciada! Estoy listo para tomar tu pedido. ¿Qué te provoca hoy?")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Limpia la memoria del usuario."""
    context.user_data.clear()
    await update.message.reply_text("¡Entendido! He borrado todo. Cuando quieras empezar de nuevo, solo tienes que hablarme.")
