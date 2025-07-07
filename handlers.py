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
            logger.info(f"IA ha finalizado el pedido para el usuario {user_id}")
            try:
                json_part = ai_response_text.split('<ORDEN_FINALIZADA>')[1].strip()
                cleaned_json_part = re.sub(r'```(json)?\s*|\s*```', '', json_part).strip()

                if not cleaned_json_part:
                    logger.warning("La IA envió la etiqueta de finalización pero no el JSON.")
                    await update.message.reply_text("¡Uy! Parece que olvidé los detalles. 🤔 ¿Podrías decir 'eso es todo' una vez más?")
                    return

                order_data = json.loads(cleaned_json_part)
                order_data['costo_delivery'] = context.user_data.get('delivery_fee', 0)
                
                pedido_items_list = order_data.get("pedido_items", [])
                pedido_lines = []
                for item in pedido_items_list:
                    if isinstance(item, dict):
                        # --- LÍNEA CORREGIDA ---
                        # Ahora busca la clave "nombre" que la IA está usando.
                        line = f"- {item.get('cantidad', 1)}x {item.get('nombre', 'Artículo desconocido')}"
                        pedido_lines.append(line)
                    elif isinstance(item, str):
                        line = f"- 1x {item}"
                        pedido_lines.append(line)
                order_data['pedido_str'] = "\n".join(pedido_lines)

                summary_text, reply_markup = generate_summary(order_data, user_id)
                await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=summary_text, reply_markup=reply_markup, parse_mode='Markdown')

                await update.message.reply_text("¡Pedido completado y enviado a la cocina! Gracias por tu compra. 👨‍🍳")
                context.user_data.clear()

            except Exception as e:
                logger.error(f"Error al procesar la orden finalizada: {e}")
                await update.message.reply_text(
                    "¡Ay, caramba! Entendí que terminaste, pero los datos del pedido vinieron con un error. "
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
    original_text = query.message.text_markdown_v2
    escaped_original_text = escape_markdown(original_text, version=2)
    new_text = f"✅ *ENTREGADO* ✅\n\n~{escaped_original_text}~"
    await query.edit_message_text(text=new_text, parse_mode='MarkdownV2')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comando para iniciar o reiniciar la conversación."""
    context.user_data.clear()
    await update.message.reply_text("¡Hola! Soy ArrozinBot. ¡Tu sesión ha sido reiniciada! Estoy listo para tomar tu pedido. ¿Qué te provoca hoy?")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Limpia la memoria del usuario."""
    context.user_data.clear()
    await update.message.reply_text("¡Entendido! He borrado todo. Cuando quieras empezar de nuevo, solo tienes que hablarme.")
