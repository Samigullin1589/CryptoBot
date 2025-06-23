import logging
from aiogram import Router, Bot
from aiogram.types import Message
from bot.filters.spam_filter import SpamFilter
from bot.config.settings import settings
from bot.utils.helpers import sanitize_html

spam_router = Router()
logger = logging.getLogger(__name__)

# Применяем наш кастомный фильтр ко всем сообщениям
@spam_router.message(SpamFilter())
async def handle_spam_message(message: Message, bot: Bot):
    """
    Обрабатывает спам-сообщение: удаляет его и уведомляет администратора.
    """
    user_info = f"Пользователь: {message.from_user.full_name} (@{message.from_user.username}, ID: {message.from_user.id})"
    message_text = sanitize_html(message.text or "Сообщение без текста (например, только фото со ссылкой)")
    
    notification_text = (
        f"🚨 <b>Обнаружено и удалено спам-сообщение!</b>\n\n"
        f"<b>От:</b> {user_info}\n"
        f"<b>Чат:</b> {message.chat.title} (ID: {message.chat.id})\n"
        f"<b>Текст сообщения:</b>\n"
        f"<blockquote>{message_text}</blockquote>"
    )
    
    try:
        # Уведомляем администратора
        await bot.send_message(settings.admin_chat_id, notification_text)
    except Exception as e:
        logger.error(f"Could not send spam notification to admin: {e}")

    try:
        # Удаляем спам-сообщение
        await message.delete()
        logger.info(f"Deleted spam message from user {message.from_user.id} in chat {message.chat.id}")
    except Exception as e:
        logger.error(f"Could not delete spam message in chat {message.chat.id}: {e}")