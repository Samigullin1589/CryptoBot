import re
from datetime import timedelta, datetime

from aiogram import Router, F, Bot
# --- ИСПРАВЛЕНИЕ: Разделены импорты для соответствия aiogram 3.x ---
from aiogram.filters import Command
from aiogram.filters.chat_type import ChatTypeFilter
# -----------------------------------------------------------------
from aiogram.types import Message, ChatPermissions

# Импортируем наши сервисы, которые будут передаваться через DI
from bot.services.user_service import UserService
from bot.services.ai_service import AIService
from bot.filters.admin_filter import IsAdminFilter

# Создаем роутер специально для админских команд по борьбе со спамом
admin_spam_router = Router()

# Ограничиваем все хендлеры в этом роутере только для групповых чатов и только для администраторов
admin_spam_router.message.filter(
    ChatTypeFilter(chat_type=["group", "supergroup"]),
    IsAdminFilter()
)

def parse_duration(text: str) -> timedelta | None:
    """
    Парсит строку с временем (например, "30m", "1h", "2d") и возвращает объект timedelta.
    Возвращает None, если формат неверный.
    """
    match = re.match(r"(\d+)([mhd])", text.lower())
    if not match:
        return None
    
    value, unit = int(match.group(1)), match.group(2)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    return None

# --- Хендлеры для модерации пользователей ---

@admin_spam_router.message(Command("ban", "бан", prefix="!/"))
async def handle_ban_user(message: Message, bot: Bot, user_service: UserService, ai_service: AIService):
    """
    Обработчик команды !ban. Банит пользователя и использует его сообщение для обучения AI.
    Работает только при ответе на сообщение нарушителя.
    """
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя, которого вы хотите забанить.")
        return

    target_user = message.reply_to_message.from_user
    spam_message = message.reply_to_message
    
    try:
        # Баним пользователя в чате
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target_user.id)
        
        # Обновляем статус пользователя в нашей базе данных через сервис
        await user_service.update_user_status(user_id=target_user.id, chat_id=message.chat.id, is_banned=True)
        
        # САМОЕ ВАЖНОЕ: передаем спам-сообщение в AI-сервис для обучения
        # Это замыкает контур обратной связи
        await ai_service.learn_from_spam(spam_message)
        
        # Удаляем спам-сообщение и команду администратора
        await spam_message.delete()
        await message.delete()

        await message.answer_photo(
            photo="https://i.imgur.com/p7b4Gv7.png", # Картинка с молотом бана
            caption=f"✅ Пользователь {target_user.full_name} забанен. Сообщение использовано для обучения антиспам-системы."
        )

    except Exception as e:
        await message.reply(f"❌ Не удалось забанить пользователя. Ошибка: {e}")


@admin_spam_router.message(Command("mute", "мут", prefix="!/"))
async def handle_mute_user(message: Message, bot: Bot, user_service: UserService):
    """
    Обработчик команды !mute. Ограничивает права пользователя на определенное время.
    Пример: !mute 30m, !mute 2h, !mute 1d
    """
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя, которого вы хотите замутить.")
        return

    command_args = message.text.split()
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите длительность мута. Например: <code>!mute 30m</code> или <code>!mute 1h</code>.")
        return
        
    duration = parse_duration(command_args[1])
    if not duration:
        await message.reply("⚠️ Неверный формат времени. Используйте 'm' для минут, 'h' для часов, 'd' для дней (например, 30m, 2h, 1d).")
        return

    target_user = message.reply_to_message.from_user
    mute_end_timestamp = datetime.now() + duration

    try:
        # Ограничиваем права пользователя (запрещаем отправку сообщений)
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(), # Пустые права = полный мут
            until_date=mute_end_timestamp
        )
        
        # Обновляем статус в нашей БД
        await user_service.update_user_mute(user_id=target_user.id, chat_id=message.chat.id, mute_until=mute_end_timestamp.timestamp())
        
        await message.reply_to_message.delete()
        await message.delete()
        await message.answer(f"✅ Пользователь {target_user.full_name} замучен до {mute_end_timestamp.strftime('%Y-%m-%d %H:%M:%S')}.")

    except Exception as e:
        await message.reply(f"❌ Не удалось замутить пользователя. Ошибка: {e}")


@admin_spam_router.message(Command("unmute", "размут", prefix="!/"))
async def handle_unmute_user(message: Message, bot: Bot, user_service: UserService):
    """
    Снимает мут с пользователя.
    """
    if not message.reply_to_message:
        await message.reply("⚠️ Эту команду нужно использовать в ответ на сообщение пользователя.")
        return

    target_user = message.reply_to_message.from_user
    try:
        # Возвращаем стандартные права (может отправлять сообщения, но не медиа и ссылки)
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target_user.id,
            permissions=ChatPermissions(can_send_messages=True)
        )
        await user_service.update_user_mute(user_id=target_user.id, chat_id=message.chat.id, mute_until=0)
        await message.delete()
        await message.answer(f"✅ С пользователя {target_user.full_name} сняты ограничения.")
    except Exception as e:
        await message.reply(f"❌ Не удалось снять ограничения. Ошибка: {e}")


# --- Хендлеры для управления системой ---

@admin_spam_router.message(Command("add_stop_word", prefix="!/"))
async def handle_add_stop_word(message: Message, ai_service: AIService):
    """
    Добавляет новое стоп-слово в базу данных через AI-сервис.
    """
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово, которое нужно добавить. Например: <code>!add_stop_word казино</code>")
        return
        
    word = command_args[1].lower().strip()
    success = await ai_service.add_stop_word(word)
    
    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' добавлено в стоп-лист.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' уже было в стоп-листе.")


@admin_spam_router.message(Command("del_stop_word", prefix="!/"))
async def handle_delete_stop_word(message: Message, ai_service: AIService):
    """
    Удаляет стоп-слово из базы данных.
    """
    command_args = message.text.split(maxsplit=1)
    if len(command_args) < 2:
        await message.reply("⚠️ Укажите слово, которое нужно удалить.")
        return
        
    word = command_args[1].lower().strip()
    success = await ai_service.remove_stop_word(word)

    if success:
        await message.reply(f"✅ Слово '<code>{word}</code>' удалено из стоп-листа.")
    else:
        await message.reply(f"⚠️ Слово '<code>{word}</code>' не найдено в стоп-листе.")


@admin_spam_router.message(Command("list_stop_words", prefix="!/"))
async def handle_list_stop_words(message: Message, ai_service: AIService):
    """
    Показывает текущий список стоп-слов.
    """
    words = await ai_service.get_all_stop_words()
    if not words:
        await message.reply("🚫 Стоп-лист пуст.")
        return
        
    text = "📜 Текущие стоп-слова:\n\n" + "\n".join([f"• <code>{word}</code>" for word in words])
    await message.reply(text)

